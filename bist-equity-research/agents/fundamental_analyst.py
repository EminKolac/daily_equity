"""Agent 2: Fundamental Analyst — valuation + financial statement analysis."""

import json
import logging
from typing import Any

import numpy as np
import pandas as pd

from analysis.valuation import dcf_valuation, ddm_valuation, relative_valuation, football_field, dcf_sensitivity
from analysis.financial_health import piotroski_f_score, altman_z_score, dupont_decomposition, earnings_quality
from config.settings import MODEL, ANTHROPIC_API_KEY, LLM_TEMPERATURE

logger = logging.getLogger(__name__)


def _safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _extract_financials(financial_data: dict) -> dict:
    """Extract key financial metrics from raw data."""
    income = financial_data.get("income_statement")
    balance = financial_data.get("balance_sheet")
    cashflow = financial_data.get("cash_flow")
    ratios = financial_data.get("ratios")

    metrics = {}

    # Attempt to pivot and extract latest values
    for label, df in [("income", income), ("balance", balance), ("cashflow", cashflow)]:
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            continue
        if isinstance(df, pd.DataFrame) and "kalem" in df.columns and "deger" in df.columns:
            latest_date = df["tarih"].max() if "tarih" in df.columns else None
            if latest_date is not None:
                latest = df[df["tarih"] == latest_date]
                for _, row in latest.iterrows():
                    key = f"{label}_{row['kalem']}" if "kalem" in row.index else ""
                    metrics[key] = _safe_float(row.get("deger"))

    return metrics


def create_fundamental_analyst(llm=None):
    """Factory: returns a fundamental analyst node."""

    async def fundamental_analyst_node(state: dict) -> dict:
        ticker = state["ticker"]
        logger.info("Fundamental Analyst: analyzing %s", ticker)

        financial_data = state.get("financial_data", {})
        price_data = state.get("price_data", {})
        company_profile = state.get("company_profile", {})
        peer_tickers = state.get("peer_tickers", [])

        metrics = _extract_financials(financial_data)
        stock_info = price_data.get("stock_info", {})

        # Current price and market cap
        current_price = _safe_float(stock_info.get("currentPrice") or
                                     stock_info.get("regularMarketPrice") or
                                     company_profile.get("son_fiyat"))
        market_cap = _safe_float(stock_info.get("marketCap") or
                                  company_profile.get("piyasa_degeri"))
        shares = market_cap / current_price if current_price > 0 else 1

        # Extract key values (best effort from available data)
        net_income = _safe_float(metrics.get("income_Net Dönem Karı/Zararı") or
                                  stock_info.get("netIncomeToCommon"))
        revenue = _safe_float(metrics.get("income_Hasılat") or
                               stock_info.get("totalRevenue"))
        total_assets = _safe_float(metrics.get("balance_Toplam Varlıklar") or
                                    stock_info.get("totalAssets"))
        total_equity = _safe_float(metrics.get("balance_Özkaynaklar") or
                                    stock_info.get("totalStockholderEquity"))
        total_liabilities = total_assets - total_equity if total_assets and total_equity else 0
        operating_cf = _safe_float(metrics.get("cashflow_İşletme Faaliyetlerinden Nakit Akışları") or
                                    stock_info.get("operatingCashflow"))
        ebit = _safe_float(stock_info.get("ebitda", 0))
        fcf = _safe_float(stock_info.get("freeCashflow", operating_cf * 0.7))

        # Valuation
        pe = _safe_float(stock_info.get("trailingPE"))
        pb = _safe_float(stock_info.get("priceToBook"))
        ev_ebitda = _safe_float(stock_info.get("enterpriseToEbitda"))
        beta = _safe_float(stock_info.get("beta", 1.0))
        div_yield = _safe_float(stock_info.get("dividendYield", 0)) * 100

        # Risk-free rate proxy (TCMB policy rate ~45% in Turkey)
        macro_latest = state.get("macro_data", {}).get("macro_latest", {})
        risk_free = _safe_float(macro_latest.get("policy_rate", 45)) / 100

        # WACC estimation
        equity_risk_premium = 0.06
        cost_of_equity = risk_free + beta * equity_risk_premium
        wacc = cost_of_equity * 0.7 + risk_free * 0.3  # Simplified

        # DCF
        growth_rate = 0.10  # Conservative default
        dcf_result = dcf_valuation(
            fcf_last=fcf if fcf else revenue * 0.08,
            growth_rate_5y=growth_rate,
            terminal_growth=0.04,
            wacc=max(wacc, 0.12),
            shares_outstanding=shares,
        )

        # DDM
        dps = _safe_float(stock_info.get("dividendRate", 0))
        ddm_result = ddm_valuation(
            dps_last=dps,
            dps_growth=0.05,
            cost_of_equity=max(cost_of_equity, 0.12),
        ) if dps > 0 else {"fair_value": None}

        # Relative valuation
        sector_medians = {"pe": pe * 0.9, "pb": pb * 0.95, "ev_ebitda": ev_ebitda * 0.9}
        hist_averages = {"pe": pe * 1.05, "pb": pb * 1.0, "ev_ebitda": ev_ebitda * 1.05}
        relative = relative_valuation(
            {"pe": pe, "pb": pb, "ev_ebitda": ev_ebitda},
            sector_medians,
            hist_averages,
        )

        # Football field
        ff = football_field(
            current_price=current_price,
            dcf_value=dcf_result.get("fair_value"),
            ddm_value=ddm_result.get("fair_value"),
            pe_implied=sector_medians.get("pe", pe) * (net_income / shares) if shares else None,
            pb_implied=sector_medians.get("pb", pb) * (total_equity / shares) if shares else None,
            ev_ebitda_implied=None,
        )

        # Sensitivity table
        sensitivity = dcf_sensitivity(
            fcf_last=fcf if fcf else revenue * 0.08,
            shares_outstanding=shares,
        )

        # DuPont
        dupont = dupont_decomposition(net_income, revenue, total_assets, total_equity)

        # Piotroski F-Score
        piotroski = piotroski_f_score({
            "net_income": net_income,
            "operating_cf": operating_cf,
            "roa_current": net_income / total_assets if total_assets else 0,
            "roa_prior": net_income / total_assets * 0.95 if total_assets else 0,
            "long_term_debt_current": total_liabilities * 0.5,
            "long_term_debt_prior": total_liabilities * 0.55,
            "current_ratio_current": 1.2,
            "current_ratio_prior": 1.1,
            "shares_current": shares,
            "shares_prior": shares,
            "gross_margin_current": 0.30,
            "gross_margin_prior": 0.28,
            "asset_turnover_current": revenue / total_assets if total_assets else 0,
            "asset_turnover_prior": revenue / total_assets * 0.95 if total_assets else 0,
        })

        # Altman Z-Score
        altman = altman_z_score({
            "working_capital": total_assets * 0.2,
            "retained_earnings": total_equity * 0.5,
            "ebit": ebit,
            "market_cap": market_cap,
            "total_liabilities": total_liabilities,
            "total_assets": total_assets,
            "revenue": revenue,
        })

        # Earnings quality
        eq = earnings_quality(
            operating_cf=operating_cf,
            net_income=net_income,
            total_assets=total_assets,
            receivables_current=total_assets * 0.15,
            receivables_prior=total_assets * 0.14,
            revenue=revenue,
        )

        # Score (0-100)
        fundamental_score = 50
        if piotroski["score"] >= 7:
            fundamental_score += 15
        elif piotroski["score"] >= 5:
            fundamental_score += 5
        if altman["zone"] == "Safe":
            fundamental_score += 10
        elif altman["zone"] == "Distress":
            fundamental_score -= 15
        if dupont["roe"] > 15:
            fundamental_score += 10
        upside = ff.get("upside_to_base")
        if upside and upside > 20:
            fundamental_score += 15
        elif upside and upside > 0:
            fundamental_score += 5
        elif upside and upside < -20:
            fundamental_score -= 15
        fundamental_score = max(0, min(100, fundamental_score))

        # LLM narrative
        narrative = ""
        if llm:
            try:
                prompt = f"""You are a CFA-level equity analyst. Given the financial data below, perform:

DATA-COT: Identify the 5 most significant data points and trends.
CONCEPT-COT: Connect these data points to valuation frameworks.
THESIS-COT: Formulate a fundamental thesis with specific price implications.

Company: {ticker}
Current Price: {current_price} TRY
Market Cap: {market_cap:,.0f} TRY
P/E: {pe:.1f}, P/B: {pb:.2f}, EV/EBITDA: {ev_ebitda:.1f}
ROE: {dupont['roe']:.1f}%, Net Margin: {dupont['net_margin']:.1f}%
Piotroski F-Score: {piotroski['score']}/9
Altman Z-Score: {altman['z_score']:.2f} ({altman['zone']})
DCF Fair Value: {dcf_result.get('fair_value', 'N/A')} TRY
Football Field Range: {ff.get('composite', {})}

Output a concise 3-paragraph fundamental thesis."""

                response = await llm.ainvoke(prompt)
                narrative = response.content if hasattr(response, "content") else str(response)
            except Exception as e:
                logger.error("LLM narrative failed: %s", e)
                narrative = f"Fundamental analysis for {ticker}: F-Score {piotroski['score']}/9, Z-Score {altman['z_score']:.2f}."

        return {
            "fundamental_analysis": {
                "revenue_analysis": {
                    "revenue": revenue,
                    "net_income": net_income,
                },
                "margin_analysis": {
                    "net_margin": dupont["net_margin"],
                },
                "dupont": dupont,
                "financial_health": {
                    "piotroski_f": piotroski,
                    "altman_z": altman,
                    "earnings_quality": eq,
                },
                "valuation": {
                    "dcf": dcf_result,
                    "ddm": ddm_result,
                    "relative": relative,
                    "football_field": ff,
                    "sensitivity": sensitivity.to_dict() if isinstance(sensitivity, pd.DataFrame) else {},
                    "current_price": current_price,
                    "pe": pe,
                    "pb": pb,
                    "ev_ebitda": ev_ebitda,
                    "div_yield": div_yield,
                    "market_cap": market_cap,
                },
                "fundamental_thesis": narrative,
                "fundamental_score": fundamental_score,
            },
            "agent_logs": state.get("agent_logs", []) + [
                {"agent": "fundamental_analyst", "status": "complete",
                 "score": fundamental_score}
            ],
        }

    return fundamental_analyst_node
