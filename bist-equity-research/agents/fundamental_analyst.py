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
    """Extract key financial metrics from raw data.

    Handles both evofin MCP data (kalem/deger format) and İş Yatırım data.
    """
    income = financial_data.get("income_statement")
    balance = financial_data.get("balance_sheet")
    cashflow = financial_data.get("cash_flow")
    ratios = financial_data.get("ratios")

    metrics = {}

    # Extract from evofin-style DataFrames (kalem/deger columns)
    for label, df in [("income", income), ("balance", balance), ("cashflow", cashflow)]:
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            continue
        if not isinstance(df, pd.DataFrame):
            continue
        if "kalem" in df.columns and "deger" in df.columns:
            latest_date = df["tarih"].max() if "tarih" in df.columns else None
            if latest_date is not None:
                latest = df[df["tarih"] == latest_date]
                for _, row in latest.iterrows():
                    kalem = row.get("kalem", "")
                    if kalem:
                        metrics[f"{label}_{kalem}"] = _safe_float(row.get("deger"))

    # Also extract quarterly time series for trend analysis
    if isinstance(income, pd.DataFrame) and not income.empty and "kalem" in income.columns:
        try:
            pivoted = income.pivot_table(
                index="tarih", columns="kalem", values="deger", aggfunc="first"
            ).sort_index()
            if not pivoted.empty:
                # Revenue trend
                for col_name in ["Hasılat", "Net Satışlar", "Satış Gelirleri"]:
                    if col_name in pivoted.columns:
                        rev_series = pivoted[col_name].dropna()
                        if len(rev_series) >= 2:
                            metrics["revenue_yoy_growth"] = float(
                                (rev_series.iloc[-1] / rev_series.iloc[-5] - 1) * 100
                            ) if len(rev_series) >= 5 else 0
                            metrics["revenue_qoq_growth"] = float(
                                (rev_series.iloc[-1] / rev_series.iloc[-2] - 1) * 100
                            )
                        break
                # Gross margin trend
                for rev_col in ["Hasılat", "Net Satışlar", "Satış Gelirleri"]:
                    for cogs_col in ["Satışların Maliyeti (-)", "Satışların Maliyeti"]:
                        if rev_col in pivoted.columns and cogs_col in pivoted.columns:
                            rev_s = pivoted[rev_col].dropna()
                            cogs_s = pivoted[cogs_col].dropna()
                            if len(rev_s) > 0 and len(cogs_s) > 0:
                                latest_rev = float(rev_s.iloc[-1])
                                latest_cogs = abs(float(cogs_s.iloc[-1]))
                                if latest_rev > 0:
                                    metrics["gross_margin_pct"] = (latest_rev - latest_cogs) / latest_rev * 100
                            break
                    else:
                        continue
                    break
        except Exception:
            pass

    # Extract balance sheet specifics for better Piotroski/Altman inputs
    if isinstance(balance, pd.DataFrame) and not balance.empty and "kalem" in balance.columns:
        try:
            latest_date = balance["tarih"].max()
            latest_bs = balance[balance["tarih"] == latest_date]
            bs_items = dict(zip(latest_bs["kalem"], latest_bs["deger"].apply(_safe_float)))

            # Map common Turkish balance sheet items
            item_map = {
                "current_assets": ["Dönen Varlıklar"],
                "non_current_assets": ["Duran Varlıklar"],
                "total_assets": ["Toplam Varlıklar", "TOPLAM VARLIKLAR"],
                "current_liabilities": ["Kısa Vadeli Yükümlülükler"],
                "non_current_liabilities": ["Uzun Vadeli Yükümlülükler"],
                "total_equity": ["Özkaynaklar", "Ana Ortaklık Payları"],
                "total_liabilities": ["Toplam Yükümlülükler"],
                "retained_earnings": ["Geçmiş Yıllar Kârları/Zararları"],
                "paid_in_capital": ["Ödenmiş Sermaye"],
                "trade_receivables": ["Ticari Alacaklar"],
                "long_term_debt": ["Finansal Borçlar"],
            }
            for metric_key, tr_names in item_map.items():
                for name in tr_names:
                    if name in bs_items:
                        metrics[f"bs_{metric_key}"] = bs_items[name]
                        break

            # Prior period for Piotroski comparison
            dates = sorted(balance["tarih"].unique())
            if len(dates) >= 2:
                prior_date = dates[-2]
                prior_bs = balance[balance["tarih"] == prior_date]
                prior_items = dict(zip(prior_bs["kalem"], prior_bs["deger"].apply(_safe_float)))
                for metric_key, tr_names in item_map.items():
                    for name in tr_names:
                        if name in prior_items:
                            metrics[f"bs_prior_{metric_key}"] = prior_items[name]
                            break
        except Exception:
            pass

    # Extract cash flow items
    if isinstance(cashflow, pd.DataFrame) and not cashflow.empty and "kalem" in cashflow.columns:
        try:
            latest_date = cashflow["tarih"].max()
            latest_cf = cashflow[cashflow["tarih"] == latest_date]
            cf_items = dict(zip(latest_cf["kalem"], latest_cf["deger"].apply(_safe_float)))
            cf_map = {
                "operating_cf": ["İşletme Faaliyetlerinden Nakit Akışları"],
                "investing_cf": ["Yatırım Faaliyetlerinden Nakit Akışları"],
                "financing_cf": ["Finansman Faaliyetlerinden Nakit Akışları"],
                "capex": ["Maddi ve Maddi Olmayan Duran Varlık Alımları",
                          "Maddi Duran Varlık Alımından Kaynaklanan Nakit Çıkışları"],
            }
            for metric_key, tr_names in cf_map.items():
                for name in tr_names:
                    if name in cf_items:
                        metrics[f"cf_{metric_key}"] = cf_items[name]
                        break
        except Exception:
            pass

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

        # Extract key values — prefer evofin data, fallback to Yahoo stock_info
        net_income = _safe_float(
            metrics.get("income_Net Dönem Karı/Zararı") or
            metrics.get("income_Net Dönem Karı") or
            stock_info.get("netIncomeToCommon")
        )
        revenue = _safe_float(
            metrics.get("income_Hasılat") or
            metrics.get("income_Net Satışlar") or
            metrics.get("income_Satış Gelirleri") or
            stock_info.get("totalRevenue")
        )
        total_assets = _safe_float(
            metrics.get("bs_total_assets") or
            metrics.get("balance_Toplam Varlıklar") or
            stock_info.get("totalAssets")
        )
        total_equity = _safe_float(
            metrics.get("bs_total_equity") or
            metrics.get("balance_Özkaynaklar") or
            stock_info.get("totalStockholderEquity")
        )
        total_liabilities = _safe_float(
            metrics.get("bs_total_liabilities") or
            (total_assets - total_equity if total_assets and total_equity else 0)
        )
        operating_cf = _safe_float(
            metrics.get("cf_operating_cf") or
            metrics.get("cashflow_İşletme Faaliyetlerinden Nakit Akışları") or
            stock_info.get("operatingCashflow")
        )
        ebit = _safe_float(stock_info.get("ebitda", 0))
        capex = _safe_float(metrics.get("cf_capex", 0))
        fcf = _safe_float(
            stock_info.get("freeCashflow") or
            (operating_cf + capex if operating_cf and capex else operating_cf * 0.7 if operating_cf else 0)
        )

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

        # Use real balance sheet data for health scoring where available
        current_assets = _safe_float(metrics.get("bs_current_assets", total_assets * 0.4))
        current_liabilities = _safe_float(metrics.get("bs_current_liabilities", total_liabilities * 0.5))
        long_term_debt = _safe_float(metrics.get("bs_long_term_debt", total_liabilities * 0.5))
        retained_earnings = _safe_float(metrics.get("bs_retained_earnings", total_equity * 0.5))
        receivables = _safe_float(metrics.get("bs_trade_receivables", total_assets * 0.15))

        # Prior period data (use real if available, else estimate)
        prior_total_assets = _safe_float(metrics.get("bs_prior_total_assets", total_assets * 0.95))
        prior_long_term_debt = _safe_float(metrics.get("bs_prior_long_term_debt", long_term_debt * 1.05))
        prior_current_assets = _safe_float(metrics.get("bs_prior_current_assets", current_assets * 0.95))
        prior_current_liabilities = _safe_float(metrics.get("bs_prior_current_liabilities", current_liabilities * 0.95))
        prior_receivables = _safe_float(metrics.get("bs_prior_trade_receivables", receivables * 0.95))

        current_ratio_current = current_assets / current_liabilities if current_liabilities else 1.0
        current_ratio_prior = prior_current_assets / prior_current_liabilities if prior_current_liabilities else 1.0
        roa_current = net_income / total_assets if total_assets else 0
        roa_prior = net_income / prior_total_assets if prior_total_assets else 0
        gross_margin_current = metrics.get("gross_margin_pct", 30) / 100
        gross_margin_prior = gross_margin_current * 0.97  # Slight conservative fallback

        # Piotroski F-Score
        piotroski = piotroski_f_score({
            "net_income": net_income,
            "operating_cf": operating_cf,
            "roa_current": roa_current,
            "roa_prior": roa_prior,
            "long_term_debt_current": long_term_debt,
            "long_term_debt_prior": prior_long_term_debt,
            "current_ratio_current": current_ratio_current,
            "current_ratio_prior": current_ratio_prior,
            "shares_current": shares,
            "shares_prior": shares,
            "gross_margin_current": gross_margin_current,
            "gross_margin_prior": gross_margin_prior,
            "asset_turnover_current": revenue / total_assets if total_assets else 0,
            "asset_turnover_prior": revenue / prior_total_assets if prior_total_assets else 0,
        })

        # Altman Z-Score
        working_capital = current_assets - current_liabilities
        altman = altman_z_score({
            "working_capital": working_capital,
            "retained_earnings": retained_earnings,
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
            receivables_current=receivables,
            receivables_prior=prior_receivables,
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
