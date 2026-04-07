"""Agent 0: Orchestrator — LangGraph StateGraph coordinating all agents."""

import logging
from datetime import datetime
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from agents.data_collector import create_data_collector
from agents.fundamental_analyst import create_fundamental_analyst
from agents.technical_analyst import create_technical_analyst
from agents.macro_analyst import create_macro_analyst
from agents.sentiment_analyst import create_sentiment_analyst
from agents.thesis_writer import create_thesis_writer
from agents.report_compiler import create_report_compiler

logger = logging.getLogger(__name__)


class ResearchState(TypedDict, total=False):
    ticker: str
    report_date: str
    company_profile: dict
    financial_data: dict
    price_data: dict
    macro_data: dict
    earnings_data: dict
    isyatirim_coverage: dict
    isyatirim_financials: Any
    social_media_data: dict
    benchmark_2y: Any
    peer_tickers: list
    kap_disclosures: list
    fundamental_analysis: dict
    technical_analysis: dict
    _technical_chart_data: dict
    macro_analysis: dict
    sentiment_analysis: dict
    investment_thesis: dict
    charts: dict
    report_sections: dict
    final_pdf: bytes
    errors: list
    agent_logs: list


def build_research_graph(llm=None, mcp_client=None) -> StateGraph:
    """Build the LangGraph research pipeline.

    Execution flow:
        data_collector
          → fundamental_analyst (parallel)
          → technical_analyst  (parallel)
          → macro_analyst      (parallel)
          → sentiment_analyst  (parallel)
          → thesis_writer
          → report_compiler
          → pdf_builder
    """
    # Create agent nodes
    data_collector = create_data_collector(mcp_client=mcp_client)
    fundamental_analyst = create_fundamental_analyst(llm=llm)
    technical_analyst = create_technical_analyst(llm=llm)
    macro_analyst = create_macro_analyst(llm=llm)
    sentiment_analyst = create_sentiment_analyst(llm=llm)
    thesis_writer = create_thesis_writer(llm=llm)
    report_compiler = create_report_compiler(llm=llm)

    # Build graph
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("data_collector", data_collector)
    graph.add_node("fundamental_analyst", fundamental_analyst)
    graph.add_node("technical_analyst", technical_analyst)
    graph.add_node("macro_analyst", macro_analyst)
    graph.add_node("sentiment_analyst", sentiment_analyst)
    graph.add_node("thesis_writer", thesis_writer)
    graph.add_node("report_compiler", report_compiler)

    # Set entry point
    graph.set_entry_point("data_collector")

    # Data collector feeds all 4 analysts
    # LangGraph doesn't natively support fan-out to parallel then join,
    # so we chain sequentially: fundamental → technical → macro → sentiment
    # Each reads from shared state and only writes its own keys.
    graph.add_edge("data_collector", "fundamental_analyst")
    graph.add_edge("fundamental_analyst", "technical_analyst")
    graph.add_edge("technical_analyst", "macro_analyst")
    graph.add_edge("macro_analyst", "sentiment_analyst")

    # After all analysts complete → thesis writer
    graph.add_edge("sentiment_analyst", "thesis_writer")

    # Thesis → report compiler
    graph.add_edge("thesis_writer", "report_compiler")

    # Report compiler → END
    graph.add_edge("report_compiler", END)

    return graph


async def run_research_pipeline(
    ticker: str,
    llm=None,
    mcp_client=None,
) -> ResearchState:
    """Run the full research pipeline for a single ticker."""
    logger.info("Starting research pipeline for %s", ticker)

    graph = build_research_graph(llm=llm, mcp_client=mcp_client)
    app = graph.compile()

    initial_state: ResearchState = {
        "ticker": ticker,
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "company_profile": {},
        "financial_data": {},
        "price_data": {},
        "macro_data": {},
        "earnings_data": {},
        "isyatirim_coverage": {},
        "isyatirim_financials": None,
        "social_media_data": {},
        "benchmark_2y": None,
        "peer_tickers": [],
        "kap_disclosures": [],
        "fundamental_analysis": {},
        "technical_analysis": {},
        "_technical_chart_data": {},
        "macro_analysis": {},
        "sentiment_analysis": {},
        "investment_thesis": {},
        "charts": {},
        "report_sections": {},
        "final_pdf": b"",
        "errors": [],
        "agent_logs": [],
    }

    try:
        final_state = await app.ainvoke(initial_state)
    except Exception as e:
        logger.error("Pipeline failed for %s: %s", ticker, e)
        initial_state["errors"] = [f"Pipeline failure: {e}"]
        return initial_state

    logger.info("Pipeline complete for %s. Agents: %d, Errors: %d",
                ticker, len(final_state.get("agent_logs", [])),
                len(final_state.get("errors", [])))
    return final_state
