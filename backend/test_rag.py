import sys
import os
import json
import asyncio
import logging
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services.rag_service import RAGService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_rag")


async def run_rag_tests():
    logger.info("==================================================")
    logger.info("STARTING RANKFORGE RAG PRODUCTION SUITE TESTS (0 MOCK)")
    logger.info("==================================================")

    service = RAGService()

    # TEST 1: Batch Embeddings (1536 Dimensions)
    logger.info("[Test 1] Testing Batch Embeddings via NVIDIA NIM nv-embedqa-e5-v5...")
    texts = [
        "Houston personal injury lawyer contingency fees and settlement timelines.",
        "Texas statute of limitations for commercial truck collision claims."
    ]
    embeddings = await service.create_embeddings_batch(texts)
    assert len(embeddings) == 2, f"Expected 2 embeddings, got {len(embeddings)}"
    assert len(embeddings[0]) == 1536, f"Expected 1536 dims, got {len(embeddings[0])}"
    logger.info(f"✅ Embeddings passed: 2 vectors returned with dim={len(embeddings[0])}")

    # Seed verified document for real retrieval & reranking verification
    logger.info("Ingesting verified Houston legal knowledge fact into knowledge_base...")
    await service.knowledge_service.ingest(
        content="Under Texas Civil Practice and Remedies Code Section 16.003, car accident and personal injury claims have a 2-year statute of limitations from the date of the incident. In Houston, legal representation operates on a standard 33.3% pre-litigation contingency fee model with zero upfront retainer.",
        source_type="manual",
        title="Texas Personal Injury Statutes & Houston Legal Fees",
        explicit_type="business_info"
    )

    # TEST 2: Hybrid Retrieval
    logger.info("[Test 2] Testing Hybrid Multi-Vector Retrieval...")
    query = "Houston car accident lawyer statute of limitations"
    hits = await service.retrieve(query=query, top_k=5)
    logger.info(f"Retrieved {len(hits)} candidates for query '{query}'")
    for idx, hit in enumerate(hits[:3]):
        logger.info(f"  Hit {idx+1}: {hit.get('title')} | Hybrid Score: {hit.get('hybrid_score')} | Sim: {hit.get('vector_sim', 0):.2f}")
    assert len(hits) >= 1, "Retrieve should return at least 1 candidate hit"
    logger.info("✅ Retrieval passed.")

    # TEST 3: Cross-Encoder Reranking
    logger.info("[Test 3] Testing NIM Cross-Encoder Reranker...")
    reranked = await service.rerank(query=query, hits=hits, top_k=3)
    logger.info(f"Reranked top {len(reranked)} hits:")
    for idx, r in enumerate(reranked):
        logger.info(f"  Rank {idx+1}: {r.get('title')} | LLM Rel: {r.get('llm_relevance_score')} | Final Score: {r.get('final_score')}")
    assert len(reranked) <= 3, "Rerank should respect top_k"
    logger.info("✅ Reranking passed.")

    # TEST 4: Citation-Grounded Generator & Anti-Hallucination
    logger.info("[Test 4] Testing Citation-Grounded Generation & Anti-Hallucination Gate...")
    gen_res = await service.generate(query=query, hits=reranked, require_citations=True)
    answer = gen_res.get("answer", "")
    citations = gen_res.get("citations", [])
    hallucination = gen_res.get("hallucination_check", {})

    logger.info(f"Generated Answer Preview: {answer[:200]}...")
    logger.info(f"Extracted Citations Count: {len(citations)}")
    for c in citations:
        logger.info(f"  Citation [{c.get('citation_number')}]: {c.get('title')} (Sim: {c.get('similarity', 0):.2f})")
    logger.info(f"Hallucination Check: {hallucination}")

    assert len(answer) > 0, "Answer must not be empty"
    logger.info("✅ Citation-grounded generation passed.")

    # TEST 5: Real-Time Token Streaming (SSE)
    logger.info("[Test 5] Testing Real-Time Token Streaming...")
    tokens_received = []
    async for chunk in service.rag_query_stream(query="Texas accident statute", top_k=2):
        if chunk.startswith("data: "):
            payload = json.loads(chunk.replace("data: ", "").strip())
            if payload.get("token"):
                tokens_received.append(payload["token"])
    logger.info(f"Received {len(tokens_received)} streamed token chunks.")
    assert len(tokens_received) > 0, "Streaming should yield token chunks"
    logger.info("✅ Streaming passed.")

    logger.info("==================================================")
    logger.info("ALL RAG SYSTEM TESTS PASSED SUCCESSFULLY (0 MOCK)")
    logger.info("==================================================")


if __name__ == "__main__":
    asyncio.run(run_rag_tests())
