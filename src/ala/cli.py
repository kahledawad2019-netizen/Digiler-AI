"""ALA command-line interface — the human/ops entry point to the KB infrastructure.

    ala init
    ala register <path> --track T --course C --module M --title "..." [--doc-type ...]
    ala stats
    ala list [--track ... --course ... --language ... --doc-type ... --status ...]
    ala show <resource_id>
    ala events <resource_id>
    ala scan [--root knowledge_base/raw]
    ala validate (<resource_id> | --all)

Deliberately built on argparse only (no click/typer) to honour "avoid
unnecessary dependencies".
"""

from __future__ import annotations

import argparse
import json
import sys

from ala.catalog.repository import KnowledgeCatalog
from ala.config.settings import load_settings
from ala.context.service import ProjectContextService
from ala.core.enums import DocType
from ala.ingestion import IngestionPipeline, ResourceClassification
from ala.metadata.validation import ValidationContext, ValidationPipeline
from ala.registry.change_detection import ChangeDetector
from ala.registry.registry import ResourceRegistry


def _catalog(settings) -> KnowledgeCatalog:
    cat = KnowledgeCatalog.from_settings(settings)
    cat.initialize()
    return cat


def cmd_init(args, settings) -> int:
    for rel in (
        settings.paths.raw_dir,
        settings.paths.derived_dir,
        settings.paths.incoming_dir,
        settings.paths.quarantine_dir,
    ):
        settings.abspath(rel).mkdir(parents=True, exist_ok=True)
    _catalog(settings).close()
    print(f"Initialized catalog at {settings.catalog_db_path}")
    return 0


def cmd_register(args, settings) -> int:
    reg = ResourceRegistry.from_settings(settings)
    # Auto-refresh the published Project Context on change (Task 5).
    reg.on_change = ProjectContextService(settings, reg.catalog).refresh
    meta = reg.register(
        args.path,
        track=args.track,
        course=args.course,
        module=args.module,
        title=args.title,
        doc_type=args.doc_type,
        role=args.role,
        language=args.language,
        slug=args.slug,
        week=args.week,
        lecture=args.lecture,
        update=args.update,
    )
    print(f"Registered {meta.resource_id} (v{meta.lifecycle.version})")
    reg.close()
    return 0


def cmd_ingest(args, settings) -> int:
    pipe = IngestionPipeline.default(settings)
    cls = ResourceClassification(
        track=args.track, course=args.course, module=args.module, title=args.title,
        doc_type=DocType(args.doc_type),
    )
    res = pipe.ingest_path(args.path, cls)
    print(res.summary())
    for o in res.outcomes:
        print(f"    [{o.level.value:<7}] {o.stage}: {o.message}")
    pipe.registry.close()
    return 0 if res.ok else 1


def cmd_ingest_dir(args, settings) -> int:
    pipe = IngestionPipeline.default(settings)
    results = pipe.ingest_directory(args.root)

    chunked = 0
    if args.chunk:
        from ala.retrieval.chunking import ChunkingService

        svc = ChunkingService(settings, registry=pipe.registry)
        for r in results:
            if r.ok and r.resource is not None:
                svc.chunk_resource(r.resource)
                chunked += 1

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status.value] = status_counts.get(r.status.value, 0) + 1
        if not r.ok:
            print(r.summary())              # surface only failures in bulk runs
    print(f"\nstatus: {status_counts}")
    ok = sum(1 for r in results if r.ok)
    print(f"{ok}/{len(results)} ingested; {chunked} chunked.")
    pipe.registry.close()
    return 0


def cmd_import_corpus(args, settings) -> int:
    from ala.ingestion.importer import CorpusImporter

    importer = CorpusImporter(settings)
    plan = importer.plan(args.source)
    print("Import plan:", json.dumps(plan.summary(), indent=2))
    if args.dry_run:
        for item in plan.items:
            if item.disposition.value in ("quarantine",) or (
                item.disposition.value == "skip" and item.reason not in
                ("skipped type .zip", "skipped type .mhtml")
            ):
                print(f"  {item.disposition.value:<13} {item.reason:<28} {item.source.name}")
        return 0

    registry = ResourceRegistry.from_settings(settings)
    report = importer.execute(plan, registry=registry)
    registry.close()
    print(f"copied={report.copied} datasets_registered={report.datasets_registered} "
          f"quarantined={report.quarantined} skipped={report.skipped}")
    print("by_course:", json.dumps(report.by_course, indent=2, ensure_ascii=False))
    return 0


def cmd_embed(args, settings) -> int:
    if args.benchmark:
        from ala.retrieval.embedding.report import run_report

        keys = [k.strip() for k in args.models.split(",")] if args.models else None
        out = run_report(settings, keys, sample_n=args.sample)
        print(f"Benchmark report + figures written to: {out}")
        return 0

    from ala.retrieval.embedding import EmbeddingService
    from ala.retrieval.embedding.factory import get_embedder

    registry = ResourceRegistry.from_settings(settings)
    embedder = get_embedder(args.model) if args.model else None
    svc = EmbeddingService(settings, embedder=embedder, registry=registry)
    if args.all:
        counts = svc.embed_all()
        print(f"Embedded {len(counts)} resources / {sum(counts.values())} chunks "
              f"with {svc.embedder.model_id} ({svc.embedder.version})")
    elif args.resource:
        recs = svc.embed_resource(args.resource)
        print(f"Embedded {len(recs)} chunks for {args.resource}")
    else:
        print("Specify --all, --resource <id>, or --benchmark", file=sys.stderr)
        registry.close()
        return 1
    registry.close()
    return 0


def _model_dim(settings, model):
    for m in sorted(settings.derived_path.glob(f"*/embeddings/{model}.manifest.json")):
        return json.loads(m.read_text(encoding="utf-8"))["dim"]
    return None


def cmd_index(args, settings) -> int:
    from ala.retrieval.embedding.config import EmbeddingConfig
    from ala.retrieval.vectorstore import VectorIndexer, get_vector_store

    model = args.model or EmbeddingConfig.from_settings(settings).default_model

    if args.benchmark:
        from ala.retrieval.vectorstore.report import run_report

        out = run_report(settings, model, limit=args.limit)
        print(f"Qdrant benchmark report + figures: {out}")
        return 0

    dim = _model_dim(settings, model)
    if dim is None:
        from ala.retrieval.embedding.factory import get_embedder
        dim = get_embedder(model).dim
    store = get_vector_store(settings, dim=dim)
    if getattr(args, "recreate", False):
        store.ensure_collection(dim, recreate=True)   # drop + rebuild (e.g. new model)
    try:
        if args.health:
            print(json.dumps(store.health(), indent=2, default=str))
            return 0
        if args.stats:
            print(json.dumps(store.stats(), indent=2, default=str))
            return 0
        if args.search:
            from ala.retrieval.embedding.factory import get_embedder

            qv = get_embedder(model, hashing_dim=dim).embed_query(args.search)
            filters = dict(p.split("=", 1) for p in args.filter if "=" in p) or None
            for h in store.search(qv, top_k=args.top_k, filters=filters):
                loc = h.payload.get("heading") or (h.payload.get("section_path") or [""])[-1]
                print(f"{h.score:.3f}  {h.payload.get('course')}/{h.payload.get('module')}  "
                      f"{h.chunk_id}  {loc}")
            return 0

        registry = ResourceRegistry.from_settings(settings)
        indexer = VectorIndexer(settings, store, model, registry=registry)
        if args.resource:
            print(f"Indexed {indexer.index_resource(args.resource)} vectors for {args.resource}")
        else:
            counts = indexer.index_all()
            print(f"Indexed {sum(counts.values())} vectors across {len(counts)} resources")
        registry.close()
        print(json.dumps(store.stats(), indent=2, default=str))
        return 0
    finally:
        store.close()


def cmd_bm25(args, settings) -> int:
    from ala.retrieval.bm25.builder import build_bm25_from_corpus
    from ala.retrieval.bm25.index import BM25Index
    from ala.retrieval.search.config import BM25FileConfig

    cfg = BM25FileConfig.from_settings(settings)
    path = settings.abspath(cfg.location)
    if args.action == "build":
        index = build_bm25_from_corpus(settings, k1=cfg.k1, b=cfg.b, min_token_len=cfg.min_token_len)
        index.save(path)
        print(f"BM25 index built -> {path}")
        print(json.dumps(index.stats(), indent=2))
    else:
        if not (path / "index.pkl").is_file():
            print("No BM25 index; run `ala bm25 build`.", file=sys.stderr)
            return 1
        print(json.dumps(BM25Index.load(path).stats(), indent=2))
    return 0


def cmd_retrieve(args, settings) -> int:
    if args.benchmark:
        from ala.retrieval.evaluation.report import run_report

        out = run_report(settings, n=args.n)
        print(f"Retrieval evaluation report + figures: {out}")
        return 0

    if not args.query:
        print("Provide a query (or use --benchmark)", file=sys.stderr)
        return 1

    from ala.retrieval.search.config import RetrievalConfig
    from ala.retrieval.search.factory import build_retrievers
    from ala.retrieval.search.normalize import normalize_query

    cfg = RetrievalConfig.from_settings(settings)
    if args.rerank:
        cfg.rerank_enabled = True
    retr = build_retrievers(settings, cfg)
    try:
        filters = dict(p.split("=", 1) for p in args.filter if "=" in p) or None
        if args.dense:
            results = retr.dense.retrieve(normalize_query(args.query), top_k=args.top_k, filters=filters)
        elif args.bm25:
            results = retr.bm25.retrieve(normalize_query(args.query), top_k=args.top_k, filters=filters)
        else:
            results = retr.hybrid.retrieve(args.query, top_k=args.top_k, filters=filters)
        for r in results:
            print(f"{r.score:.4f}  {r.citation()}  {r.chunk_id}")
    finally:
        retr.close()
    return 0


def cmd_evidence(args, settings) -> int:
    if args.benchmark:
        from ala.retrieval.evidence.report import run_report

        out = run_report(settings, top_k=args.top_k)
        print(f"Evidence benchmark report + figures: {out}")
        return 0
    if not args.query:
        print("Provide a query (or use --benchmark)", file=sys.stderr)
        return 1

    from ala.retrieval.evidence.formatter import EvidenceFormatter
    from ala.retrieval.evidence.serializer import EvidenceSerializer
    from ala.retrieval.evidence.service import EvidenceService
    from ala.retrieval.evidence.validator import EvidenceValidator

    svc = EvidenceService(settings)
    try:
        filters = dict(p.split("=", 1) for p in args.filter if "=" in p) or None
        pkg = svc.build(args.query, top_k=args.top_k, filters=filters)
    finally:
        svc.close()

    if args.json:
        print(EvidenceSerializer.to_json(pkg))
    else:
        valid = EvidenceValidator().validate(pkg)
        print(f"overall_confidence={pkg.overall_confidence}  valid={valid.ok}  {pkg.stats}\n")
        print(EvidenceFormatter().to_context(pkg, include_scores=True))
    return 0


def cmd_graph(args, settings) -> int:
    from ala.graph.store import GraphStore

    loc = (settings.graph or {}).get("location", "data/graph/concept_graph.db")
    path = settings.abspath(loc)

    if args.action == "build":
        from ala.graph.report import build_and_persist

        graph, db = build_and_persist(settings)
        print(f"Concept graph built -> {db}")
        print(json.dumps(graph.statistics(), indent=2, ensure_ascii=False))
        return 0
    if args.action == "report":
        from ala.graph.report import run_report

        print(f"Graph report + figures: {run_report(settings)}")
        return 0
    if args.action == "concepts":
        from ala.graph.concept_report import run_concept_report

        out = run_concept_report(settings, embedder_key=args.model)
        print(f"Concept-quality report + figures: {out}")
        return 0
    if not GraphStore(path).exists():
        print("No concept graph; run `ala graph build`.", file=sys.stderr)
        return 1
    graph = GraphStore(path).load()
    if args.action == "stats":
        print(json.dumps(graph.statistics(), indent=2, ensure_ascii=False))
        return 0
    # show
    cid = args.concept if (args.concept or "").startswith("concept:") else f"concept:{args.concept}"
    node = graph.node(cid)
    if node is None:
        print(f"Concept not found: {cid}", file=sys.stderr)
        return 1
    print(f"{node.label}  ({cid})")
    for nb, etype, data in graph.neighbors(cid):
        lbl = graph.node(nb).label if graph.node(nb) else nb
        print(f"  --{etype}--> {lbl}  (w={data.get('weight')})")
    return 0


def cmd_graph_retrieve(args, settings) -> int:
    if args.benchmark:
        from ala.retrieval.graphsearch.benchmark import run_graph_benchmark

        out = run_graph_benchmark(settings, n=args.n, example_query=args.example)
        print(f"Graph-retrieval benchmark + figures -> {out}")
        return 0

    if not args.query:
        print("Provide a query, or use --benchmark.", file=sys.stderr)
        return 2

    from ala.retrieval.graphsearch.config import GraphRetrievalConfig
    from ala.retrieval.graphsearch.factory import build_graph_retriever

    cfg = GraphRetrievalConfig.from_settings(settings)
    if args.hops is not None:
        cfg.max_hops = args.hops
    bundle = build_graph_retriever(settings, config=cfg)
    try:
        res = bundle.graph.retrieve_with_graph(args.query, top_k=args.top_k)
    finally:
        bundle.close()

    print(f"query: {res.query}   {res.stats}\n")
    print("== graph evidence (concept expansion) ==")
    for g in res.graph_evidence:
        arrow = " -> ".join(g.path)
        print(f"  [{g.hop}h {g.relationship:12}] {g.concept:32}  score={g.score:.3f}  path: {arrow}")
    print("\n== chunk evidence (graph-aware ranking) ==")
    for r in res.chunks:
        print(f"  #{r.rank} {r.payload.get('resource_id', r.chunk_id):40} "
              f"score={r.score:.4f}  {r.component_scores}")
    return 0


def cmd_graphrag(args, settings) -> int:
    if args.benchmark:
        from ala.rag.benchmark import run_graphrag_benchmark

        out = run_graphrag_benchmark(settings, n=args.n, example_query=args.example)
        print(f"GraphRAG benchmark + figures -> {out}")
        return 0

    if not args.query:
        print("Provide a question, or use --benchmark.", file=sys.stderr)
        return 2

    from ala.rag.pipeline import GraphRAGService

    svc = GraphRAGService(settings)
    try:
        ans, ctx, pkg = svc.answer_with_context(args.query, top_k=args.top_k)
    finally:
        svc.close()

    if args.json:
        print(json.dumps({"answer": ans.to_dict(), "context": ctx.to_dict()},
                         indent=2, ensure_ascii=False))
        return 0

    print(f"Q: {ans.question}\n")
    print(f"A: {ans.answer}\n")
    print("Citations:")
    for c in ans.citations:
        loc = c.locator()
        print(f"  [{c.cid}] {c.label}" + (f"  ({loc})" if loc else "") +
              f"  conf={c.confidence:.2f}")
    g = ans.grounding
    print(f"\ngrounding={g['grounding_ratio']}  citations_valid={g['citation_valid']}  "
          f"generator={ans.generator}  confidence={ans.confidence}  {ans.stats}")
    print("\nReasoning trace:")
    for step in ans.reasoning_trace:
        print(f"  - {step}")
    return 0


def cmd_research(args, settings) -> int:
    if args.benchmark:
        from ala.research.benchmark import run_research_benchmark

        out = run_research_benchmark(settings)
        print(f"Research-Mode benchmark + figures -> {out}")
        return 0

    if not args.query:
        print("Provide a question, or use --benchmark.", file=sys.stderr)
        return 2

    from ala.research.controller import ResearchModeController

    ctrl = ResearchModeController.from_settings(settings)

    def _approve(question, sources):
        return args.save

    try:
        res = ctrl.research(args.query, approve=_approve if args.save else None, top_k=args.top_k)
    finally:
        ctrl.close()

    print(f"Q: {res.question}\n")
    print(f"A: {res.answer}\n")
    c = res.confidence
    print(f"confidence={c.score} level={c.level} needs_research={c.needs_research} "
          f"used_web={res.used_web}")
    if res.sources:
        print("\nWeb sources (ranked):")
        for s in res.sources:
            print(f"  - {s['domain']:24} trust={s['trust']}  {s['title'][:50]}")
    if res.ingested:
        print(f"\nGrew the Knowledge Base with: {', '.join(res.ingested)}")
    print(f"\nsession={res.session_id}  stats={res.stats}")
    return 0


def cmd_llm(args, settings) -> int:
    from ala.llm.factory import make_provider
    from ala.llm.provider import LLMConfig

    cfg = LLMConfig.from_settings(settings)
    provider = make_provider(config=cfg)
    reachable = bool(provider and provider.available())
    if args.prompt:
        if not reachable:
            print(f"LLM provider '{cfg.provider}' ({cfg.model}) not reachable at {cfg.base_url}.",
                  file=sys.stderr)
            return 1
        print(provider.complete(args.prompt))
        return 0
    print(f"provider   : {cfg.provider}")
    print(f"model      : {cfg.model}  (supported: {', '.join(cfg.supported)})")
    print(f"base_url   : {cfg.base_url}")
    print(f"reachable  : {reachable}")
    if not reachable:
        print("  (start Ollama and `ollama pull qwen3`; generation falls back to extractive meanwhile)")
    return 0


def cmd_functions(args, settings) -> int:
    if args.benchmark:
        from ala.functions.benchmark import run_functions_benchmark

        out = run_functions_benchmark(settings)
        print(f"Function Calling benchmark + figures -> {out}")
        return 0

    from ala.functions.service import FunctionService

    if args.list:
        # schemas don't need the heavy services for calculator/python, but the
        # registry wires everything; build the service to list the full catalog.
        svc = FunctionService(settings)
        try:
            print(json.dumps(svc.schemas(), indent=2, ensure_ascii=False))
        finally:
            svc.close()
        return 0

    if not args.name:
        print("Provide a function name + --arg k=v, or --list / --benchmark.", file=sys.stderr)
        return 2

    kwargs = {}
    for pair in args.arg:
        k, _, v = pair.partition("=")
        kwargs[k] = v

    svc = FunctionService(settings)
    try:
        result = svc.call(args.name, **kwargs)
    finally:
        svc.close()
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, default=str))
    return 0 if result.ok else 1


def cmd_agents(args, settings) -> int:
    if args.benchmark:
        from ala.agents.benchmark import run_agents_benchmark

        out = run_agents_benchmark(settings)
        print(f"AI Agents benchmark + figures -> {out}")
        return 0

    if not args.text and not args.session:
        print("Provide a request, --session <concept>, or --benchmark.", file=sys.stderr)
        return 2

    from ala.agents.service import AgentService

    svc = AgentService(settings)
    try:
        if args.session:
            ss = svc.study_session(args.student, args.session)
            print(f"Study session on '{ss['concept']}':")
            for step in ss["transcript"]:
                print(f"  [{step['agent']}] {step['output'][:100]}")
            print(f"  outcome: correct={ss['correct']} mastery_after={ss['mastery_after']}")
        else:
            r = svc.ask(args.text, student_id=args.student, concept=args.concept)
            print(f"[{r.agent} agent | routed_to={r.data.get('routed_to')}]")
            print(r.output)
            if r.citations:
                print("  citations:", ", ".join(c.get("label") or c.get("cid", "") for c in r.citations[:4]))
    finally:
        svc.close()
    return 0


def cmd_rl(args, settings) -> int:
    if args.benchmark:
        from ala.rl.benchmark import run_rl_benchmark

        out = run_rl_benchmark(settings)
        print(f"RL Adaptive Learning benchmark + figures -> {out}")
        return 0

    if not args.concept:
        print("Provide --concept <concept_id>, or use --benchmark.", file=sys.stderr)
        return 2

    from ala.rl.controller import AdaptiveController
    from ala.student.model import StudentModel

    sm = StudentModel(settings)
    ctrl = AdaptiveController(settings, sm)
    try:
        sm.get_or_create(args.student)
        diff = ctrl.choose_difficulty(args.student, args.concept, explore=False)
        style = ctrl.choose(args.student, args.concept, decision="explanation_style", explore=False)
        qtype = ctrl.choose(args.student, args.concept, decision="question_type", explore=False)
        if args.quiz is not None:
            it = ctrl.record_outcome(args.student, args.concept, diff, correct=args.quiz == "correct",
                                     response_time=args.time)
            print(f"Recorded outcome: reward={it.reward}, mastery {it.mastery_before}->{it.mastery_after}")
    finally:
        ctrl.close()
    print(f"Adaptive policy for {args.student} / {args.concept}:")
    print(f"  quiz difficulty : {diff['action']} ({diff['difficulty']})")
    print(f"  explanation     : {style['action']}")
    print(f"  question type   : {qtype['action']}")
    return 0


def cmd_planner(args, settings) -> int:
    if args.benchmark:
        from ala.planner.benchmark import run_planner_benchmark

        out = run_planner_benchmark(settings)
        print(f"Study Planner benchmark + figures -> {out}")
        return 0

    from ala.planner.models import StudyGoal
    from ala.planner.service import StudyPlannerService

    goal = StudyGoal(description=args.goal, deadline_days=args.days,
                     minutes_per_day=args.minutes, course=args.course)
    svc = StudyPlannerService(settings)
    try:
        if args.html:
            path = svc.export_html(args.student, goal, settings.abspath(args.html))
            print(f"Study plan written to {path}")
        plan = svc.plan(args.student, goal)
    finally:
        svc.close()

    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
        return 0
    s = plan.stats
    print(f"Study plan — {plan.goal}")
    print(f"  {s['n_days_used']}/{s['deadline_days']} days, {s['total_minutes']} min, "
          f"{int(s['weak_minutes_share']*100)}% on weak concepts, fits={s['fits_deadline']}")
    for d in plan.days[:5]:
        acts = ", ".join(f"{a.type}:{a.concept[:18]}" for a in d.activities)
        print(f"  Day {d.day} ({d.minutes}m): {acts}")
    return 0


def cmd_dashboard(args, settings) -> int:
    if args.benchmark:
        from ala.dashboard.benchmark import run_dashboard_benchmark

        out = run_dashboard_benchmark(settings)
        print(f"Learning Analytics Dashboard + figures -> {out}")
        return 0

    from ala.dashboard.service import DashboardService

    svc = DashboardService(settings)
    try:
        if args.html:
            path = svc.export_html(args.student, settings.abspath(args.html))
            print(f"Dashboard written to {path}")
        data = svc.build(args.student)
    finally:
        svc.close()

    if args.json:
        print(json.dumps(data.to_dict(), indent=2, ensure_ascii=False))
        return 0
    s = data.summary
    print(f"Dashboard — {args.student}: overall mastery {s.get('overall_mastery')}, "
          f"weak {s.get('n_weak')}, strong {s.get('n_strong')}, "
          f"{data.time_spent.get('total_minutes', 0):.0f} min")
    print("Recommendations:")
    for r in data.recommendations[:6]:
        print(f"  [{r['kind']}] {r['concept']} — {r['reason']}")
    return 0


def cmd_student(args, settings) -> int:
    if args.benchmark:
        from ala.student.benchmark import run_student_benchmark

        out = run_student_benchmark(settings)
        print(f"Student Model benchmark + figures -> {out}")
        return 0

    from ala.student.model import StudentModel

    model = StudentModel(settings)
    try:
        if args.quiz is not None:
            model.get_or_create(args.student)
            e = model.record_quiz(args.student, args.concept or [], correct=args.quiz == "correct",
                                  difficulty=args.difficulty)
            print(f"Recorded quiz ({args.quiz}) for {len(e.concept_ids)} concept(s).")
        prof = model.get_or_create(args.student)
        summary = model.mastery_summary(args.student)
        print(f"Student {prof.student_id} ({prof.level}, {prof.explanation_style})")
        print(f"  overall mastery {summary['overall_mastery']}  "
              f"weak {summary['n_weak']}  strong {summary['n_strong']}  events {summary['n_events']}")
        weak = model.weak_concepts(args.student, k=8)
        if weak:
            print("  weakest:", ", ".join(f"{c.concept_id.replace('concept:','')}={c.mastery:.2f}"
                                          for c in weak))
    finally:
        model.close()
    return 0


def cmd_vision(args, settings) -> int:
    if args.benchmark:
        from ala.vision.benchmark import run_vision_benchmark

        out = run_vision_benchmark(settings)
        print(f"Vision RAG benchmark + figures -> {out}")
        return 0

    from ala.vision.ingest import VisionIngestor

    ing = VisionIngestor(settings)
    try:
        if args.figures:
            out = ing.ingest_figures(args.figures)
            what = f"{out.n_figures} figures/tables from {args.figures}"
        elif args.image:
            out = ing.ingest_image(args.image, title=args.title)
            what = f"image {args.image}"
        else:
            print("Provide --figures <resource_id> or --image <path>, or --benchmark.",
                  file=sys.stderr)
            return 2
    finally:
        ing.close()

    if not out.ok:
        print("Nothing indexed (no captioned figures / empty image).", file=sys.stderr)
        return 1
    print(f"Indexed {what} -> resource {out.resource_id} "
          f"({out.n_children} image chunks, searchable={out.searchable}, {out.total_ms} ms)")
    return 0


def cmd_video(args, settings) -> int:
    if args.benchmark:
        from ala.video.benchmark import run_video_benchmark

        out = run_video_benchmark(settings)
        print(f"Video Adapter benchmark + figures -> {out}")
        return 0

    if not args.source:
        print("Provide a video source (URL / .mp4 / .vtt), or use --benchmark.", file=sys.stderr)
        return 2

    from ala.video.ingest import VideoIngestor

    ing = VideoIngestor(settings)
    try:
        out = ing.ingest_video(args.source, title=args.title)
    finally:
        ing.close()

    if not out.ok:
        print("No transcript could be obtained (no captions/ASR available for this source).",
              file=sys.stderr)
        return 1
    print(f"Ingested video resource {out.resource_id}")
    print(f"  {out.n_cues} cues -> {out.n_segments} segments -> {out.n_children} timestamped chunks")
    print(f"  duration {out.duration}s, searchable={out.searchable}, {out.total_ms} ms")
    print(f"  stages: {out.timings_ms}")
    return 0


def cmd_citations(args, settings) -> int:
    if args.benchmark:
        from ala.explorer.benchmark import run_explorer_benchmark

        out = run_explorer_benchmark(settings, example=args.query or "what is a convolutional neural network")
        print(f"Citation Explorer report + figures -> {out}")
        return 0

    if not args.query:
        print("Provide a question, or use --benchmark.", file=sys.stderr)
        return 2

    from ala.explorer.service import CitationExplorerService

    svc = CitationExplorerService(settings)
    try:
        idx = svc.explore(args.query, top_k=args.top_k)
        if args.html:
            path = settings.abspath(args.html)
            path.parent.mkdir(parents=True, exist_ok=True)
            from ala.explorer.html import render
            path.write_text(render(idx, title=f"Citation Explorer — {args.query}"), encoding="utf-8")
    finally:
        svc.close()

    if args.json:
        print(json.dumps(idx.to_dict(), indent=2, ensure_ascii=False))
        return 0

    st = idx.stats()
    print(f"Q: {idx.query}\n{st['n_citations']} citations, {st['n_sources']} sources, "
          f"{int(st['resolvable_rate']*100)}% resolvable, {int(st['locator_coverage']*100)}% located\n")
    for n in idx.nodes:
        loc = f" ({n.locator})" if n.locator else ""
        link = n.link if n.resolvable else "unresolved"
        print(f"  [{n.cid}] {n.source_type:8} {n.title[:44]}{loc}  conf={n.confidence:.2f}")
        print(f"        -> {link}")
    if args.html:
        print(f"\nClickable explorer written to {settings.abspath(args.html)}")
    return 0


def cmd_graphrag_eval(args, settings) -> int:
    from ala.rag.evaluation import run_graphrag_evaluation

    out = run_graphrag_evaluation(settings, n=args.n, n_rag=args.n_rag)
    print(f"GraphRAG evaluation + figures -> {out}")
    return 0


def cmd_context(args, settings) -> int:
    svc = ProjectContextService.from_settings(settings)
    if args.action == "refresh":
        ctx = svc.refresh()
        print(f"Refreshed {settings.abspath(settings.paths.project_context)}")
        print(ctx.summary_line())
    else:
        import yaml

        print(yaml.safe_dump(svc.build().to_dict(), allow_unicode=True, sort_keys=False))
    svc.catalog.close()
    return 0


def cmd_stats(args, settings) -> int:
    cat = _catalog(settings)
    print(json.dumps(cat.statistics(), indent=2, ensure_ascii=False))
    cat.close()
    return 0


def cmd_list(args, settings) -> int:
    cat = _catalog(settings)
    criteria = {
        k: v
        for k, v in {
            "track": args.track,
            "course": args.course,
            "language": args.language,
            "doc_type": args.doc_type,
            "processing_status": args.status,
        }.items()
        if v
    }
    rows = cat.filter(**criteria) if criteria else cat.list_all(record_status=None)
    for r in rows:
        print(f"{r['resource_id']:<48} {r['doc_type']:<15} {r['processing_status']:<10} {r['title']}")
    print(f"\n{len(rows)} resource(s).")
    cat.close()
    return 0


def cmd_show(args, settings) -> int:
    cat = _catalog(settings)
    meta = cat.get(args.resource_id)
    if meta is None:
        print(f"Not found: {args.resource_id}", file=sys.stderr)
        cat.close()
        return 1
    print(meta.to_json())
    cat.close()
    return 0


def cmd_events(args, settings) -> int:
    cat = _catalog(settings)
    for e in cat.get_events(args.resource_id):
        print(f"{e['created_at']}  {e['event_type']:<16} v{e['version']}  {e['to_hash'] or ''}")
    cat.close()
    return 0


def cmd_scan(args, settings) -> int:
    cat = _catalog(settings)
    det = ChangeDetector(cat, settings.project_root)
    report = det.scan(root=args.root or settings.paths.raw_dir)
    print(json.dumps(report.summary(), indent=2))
    if report.to_reprocess():
        print("\nNeeds reprocessing:")
        for rid in report.to_reprocess():
            print(f"  - {rid}")
    cat.close()
    return 0


def cmd_validate(args, settings) -> int:
    cat = _catalog(settings)
    pipeline = ValidationPipeline()
    ctx = ValidationContext(
        project_root=settings.project_root,
        supported_languages=set(settings.metadata.supported_languages),
        valid_tracks=settings.valid_track_ids(),
        valid_courses=settings.valid_course_ids(),
        check_files=True,
        verify_hash=args.verify_hash,
    )
    targets = (
        [r["resource_id"] for r in cat.list_all(record_status=None)]
        if args.all
        else [args.resource_id]
    )
    rc = 0
    for rid in targets:
        meta = cat.get(rid)
        if meta is None:
            print(f"{rid}: NOT FOUND")
            rc = 1
            continue
        result = pipeline.run(meta, ctx)
        print(f"{rid}: {result.status.value.upper()}")
        for issue in result.issues:
            print(f"    [{issue.severity.value}] {issue.rule}: {issue.message}")
        if not result.ok:
            rc = 1
    cat.close()
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ala", description="ALA Knowledge Base infrastructure CLI")
    p.add_argument("--config", help="path to platform.yaml (overrides ALA_CONFIG)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create catalog DB and KB folders")

    r = sub.add_parser("register", help="register a resource")
    r.add_argument("path")
    r.add_argument("--track", required=True)
    r.add_argument("--course", required=True)
    r.add_argument("--module", required=True)
    r.add_argument("--title", required=True)
    r.add_argument("--doc-type", dest="doc_type", default="other")
    r.add_argument("--role", default="material")
    r.add_argument("--language", default="en")
    r.add_argument("--slug", default=None)
    r.add_argument("--week", type=int, default=None)
    r.add_argument("--lecture", default=None)
    r.add_argument("--update", action="store_true", help="re-version if it already exists")

    sub.add_parser("stats", help="print catalog statistics")

    l = sub.add_parser("list", help="list resources")
    l.add_argument("--track")
    l.add_argument("--course")
    l.add_argument("--language")
    l.add_argument("--doc-type", dest="doc_type")
    l.add_argument("--status", help="processing_status")

    s = sub.add_parser("show", help="print a resource's metadata")
    s.add_argument("resource_id")

    e = sub.add_parser("events", help="print a resource's event history")
    e.add_argument("resource_id")

    sc = sub.add_parser("scan", help="change-detection report")
    sc.add_argument("--root", default=None)

    v = sub.add_parser("validate", help="validate resources")
    v.add_argument("resource_id", nargs="?")
    v.add_argument("--all", action="store_true")
    v.add_argument("--verify-hash", dest="verify_hash", action="store_true")

    c = sub.add_parser("context", help="show or refresh the Project Context")
    c.add_argument("action", nargs="?", choices=["show", "refresh"], default="show")

    ing = sub.add_parser("ingest", help="run the ingestion pipeline on one file")
    ing.add_argument("path")
    ing.add_argument("--track", required=True)
    ing.add_argument("--course", required=True)
    ing.add_argument("--module", required=True)
    ing.add_argument("--title", required=True)
    ing.add_argument("--doc-type", dest="doc_type", default="other")

    ind = sub.add_parser("ingest-dir", help="discover and ingest a directory tree")
    ind.add_argument("--root", default=None)
    ind.add_argument("--chunk", action="store_true", help="also run parent-child chunking")

    imp = sub.add_parser("import-corpus", help="organize an external corpus into the managed KB")
    imp.add_argument("source")
    imp.add_argument("--dry-run", dest="dry_run", action="store_true",
                     help="print the plan without copying")

    emb = sub.add_parser("embed", help="embed chunks or benchmark embedding models")
    emb.add_argument("--model", default=None, help="embedder key (default from config)")
    emb.add_argument("--all", action="store_true", help="embed every chunked resource")
    emb.add_argument("--resource", default=None, help="embed a single resource_id")
    emb.add_argument("--benchmark", action="store_true", help="run the model benchmark + figures")
    emb.add_argument("--models", default=None, help="comma-separated model keys to benchmark")
    emb.add_argument("--sample", type=int, default=300, help="chunks to sample for benchmark")

    idx = sub.add_parser("index", help="populate / query the Qdrant vector store")
    idx.add_argument("--model", default=None, help="embedding model whose vectors to index")
    idx.add_argument("--all", action="store_true", help="index every embedded resource")
    idx.add_argument("--resource", default=None, help="index one resource_id")
    idx.add_argument("--search", default=None, help="run a similarity search for this query")
    idx.add_argument("--top-k", dest="top_k", type=int, default=10)
    idx.add_argument("--filter", action="append", default=[], help="payload filter key=value")
    idx.add_argument("--stats", action="store_true")
    idx.add_argument("--health", action="store_true")
    idx.add_argument("--benchmark", action="store_true")
    idx.add_argument("--recreate", action="store_true", help="drop + rebuild the collection")
    idx.add_argument("--limit", type=int, default=5000, help="max vectors for the benchmark")

    bm = sub.add_parser("bm25", help="build / inspect the BM25 lexical index")
    bm.add_argument("action", choices=["build", "stats"])

    rt = sub.add_parser("retrieve", help="query the retrieval engine")
    rt.add_argument("query", nargs="?")
    rt.add_argument("--dense", action="store_true", help="dense (Qdrant) only")
    rt.add_argument("--bm25", action="store_true", help="BM25 only")
    rt.add_argument("--hybrid", action="store_true", help="hybrid (default)")
    rt.add_argument("--rerank", action="store_true", help="enable cross-encoder reranking")
    rt.add_argument("--top-k", dest="top_k", type=int, default=10)
    rt.add_argument("--filter", action="append", default=[], help="payload filter key=value")
    rt.add_argument("--benchmark", action="store_true", help="run Dense/BM25/Hybrid evaluation")
    rt.add_argument("--n", type=int, default=150, help="eval queries for --benchmark")

    gr = sub.add_parser("graph", help="build / inspect the concept graph")
    gr.add_argument("action", choices=["build", "report", "concepts", "stats", "show"])
    gr.add_argument("--concept", default=None, help="concept id/label for 'show'")
    gr.add_argument("--model", default="e5-small", help="embedder for concept mining")

    grr = sub.add_parser("graph-retrieve", help="graph-aware retrieval (Stage 11)")
    grr.add_argument("query", nargs="?")
    grr.add_argument("--top-k", dest="top_k", type=int, default=10)
    grr.add_argument("--hops", type=int, default=None, help="traversal depth override")
    grr.add_argument("--benchmark", action="store_true", help="run the graph-retrieval benchmark + figures")
    grr.add_argument("--n", type=int, default=100, help="eval queries for --benchmark")
    grr.add_argument("--example", default="convolutional neural network",
                     help="example query for the traversal figures")

    grag = sub.add_parser("graphrag", help="GraphRAG: grounded, cited answer (Stage 12)")
    grag.add_argument("query", nargs="?")
    grag.add_argument("--top-k", dest="top_k", type=int, default=8)
    grag.add_argument("--json", action="store_true", help="print answer + context as JSON")
    grag.add_argument("--benchmark", action="store_true", help="run the GraphRAG benchmark + figures")
    grag.add_argument("--n", type=int, default=60, help="eval questions for --benchmark")
    grag.add_argument("--example", default="what is a convolutional neural network",
                      help="example question for the reasoning-flow figure")

    ge = sub.add_parser("graphrag-eval", help="full cross-system evaluation + ablation (Stage 13)")
    ge.add_argument("--n", type=int, default=80, help="retrieval-eval queries")
    ge.add_argument("--n-rag", dest="n_rag", type=int, default=40, help="GraphRAG-eval questions")

    lm = sub.add_parser("llm", help="LLM provider status / test (Ollama)")
    lm.add_argument("prompt", nargs="?", help="send a prompt to the configured model")

    fn = sub.add_parser("functions", help="Function Calling: safe schema-described tools (Stage 23)")
    fn.add_argument("name", nargs="?", help="function to call")
    fn.add_argument("--arg", action="append", default=[], help="argument key=value (repeatable)")
    fn.add_argument("--list", action="store_true", help="list the tool schemas")
    fn.add_argument("--benchmark", action="store_true", help="run the function-calling benchmark + figures")

    ag = sub.add_parser("agents", help="AI Agents: tutor / quiz / planner / research crew (Stage 22)")
    ag.add_argument("text", nargs="?", help="a request to route to an agent")
    ag.add_argument("--student", default="default")
    ag.add_argument("--concept", default=None)
    ag.add_argument("--session", default=None, help="run a full study session on this concept")
    ag.add_argument("--benchmark", action="store_true", help="run the agents benchmark + figures")

    rl = sub.add_parser("rl", help="RL Adaptive Learning: contextual-bandit policy (Stage 21)")
    rl.add_argument("--student", default="default", help="student id")
    rl.add_argument("--concept", default=None, help="concept id to adapt for")
    rl.add_argument("--quiz", choices=["correct", "incorrect"], default=None, help="record an outcome")
    rl.add_argument("--time", type=float, default=10.0, help="response time (s) for the outcome")
    rl.add_argument("--benchmark", action="store_true", help="run the RL benchmark + learning curves")

    pl = sub.add_parser("planner", help="Study Session Planner (Stage 20)")
    pl.add_argument("--student", default="default", help="student id")
    pl.add_argument("--goal", default="master my weak concepts", help="study goal")
    pl.add_argument("--course", default=None, help="target a whole course")
    pl.add_argument("--days", type=int, default=14, help="deadline in days")
    pl.add_argument("--minutes", type=int, default=60, help="available minutes/day")
    pl.add_argument("--html", default=None, help="write the visual plan timeline to this path")
    pl.add_argument("--json", action="store_true")
    pl.add_argument("--benchmark", action="store_true", help="run the planner benchmark + figures")

    db = sub.add_parser("dashboard", help="Learning Analytics Dashboard (Stage 19)")
    db.add_argument("--student", default="default", help="student id")
    db.add_argument("--html", default=None, help="write the interactive HTML dashboard to this path")
    db.add_argument("--json", action="store_true", help="print dashboard data as JSON")
    db.add_argument("--benchmark", action="store_true", help="run the dashboard benchmark + figures")

    st = sub.add_parser("student", help="Student Model: learner profile + mastery (Stage 18)")
    st.add_argument("--student", default="default", help="student id")
    st.add_argument("--quiz", choices=["correct", "incorrect"], default=None, help="record a quiz outcome")
    st.add_argument("--concept", action="append", default=[], help="concept id(s) for the quiz")
    st.add_argument("--difficulty", type=float, default=0.5)
    st.add_argument("--benchmark", action="store_true", help="run the student-model benchmark + figures")

    vr = sub.add_parser("vision", help="Vision RAG: figures/images as searchable evidence (Stage 17)")
    vr.add_argument("--figures", default=None, help="extract + index figures from a resource_id")
    vr.add_argument("--image", default=None, help="ingest a standalone image file")
    vr.add_argument("--title", default=None)
    vr.add_argument("--benchmark", action="store_true", help="run the vision benchmark + figures")

    vd = sub.add_parser("video", help="Video Adapter: ingest a video as timestamped resource (Stage 16)")
    vd.add_argument("source", nargs="?", help="YouTube URL / .mp4 / .vtt / .srt")
    vd.add_argument("--title", default=None)
    vd.add_argument("--benchmark", action="store_true", help="run the video benchmark + figures")

    ce = sub.add_parser("citations", help="Citation Explorer: navigable, clickable citations (Stage 15)")
    ce.add_argument("query", nargs="?")
    ce.add_argument("--top-k", dest="top_k", type=int, default=8)
    ce.add_argument("--html", default=None, help="write a clickable HTML explorer to this path")
    ce.add_argument("--json", action="store_true", help="print the citation index as JSON")
    ce.add_argument("--benchmark", action="store_true", help="run the citation benchmark + figures")

    rs = sub.add_parser("research", help="Research Mode: confidence-gated web fallback (Stage 14)")
    rs.add_argument("query", nargs="?")
    rs.add_argument("--top-k", dest="top_k", type=int, default=8)
    rs.add_argument("--save", action="store_true", help="approve growing the KB with web sources")
    rs.add_argument("--benchmark", action="store_true", help="run the Research-Mode benchmark + figures")

    ev = sub.add_parser("evidence", help="build a cited Evidence Package for a query")
    ev.add_argument("query", nargs="?")
    ev.add_argument("--top-k", dest="top_k", type=int, default=8)
    ev.add_argument("--filter", action="append", default=[], help="payload filter key=value")
    ev.add_argument("--json", action="store_true", help="print the full package as JSON")
    ev.add_argument("--benchmark", action="store_true", help="benchmark + figures")

    return p


_DISPATCH = {
    "init": cmd_init,
    "register": cmd_register,
    "stats": cmd_stats,
    "list": cmd_list,
    "show": cmd_show,
    "events": cmd_events,
    "scan": cmd_scan,
    "validate": cmd_validate,
    "context": cmd_context,
    "ingest": cmd_ingest,
    "ingest-dir": cmd_ingest_dir,
    "import-corpus": cmd_import_corpus,
    "embed": cmd_embed,
    "index": cmd_index,
    "bm25": cmd_bm25,
    "retrieve": cmd_retrieve,
    "evidence": cmd_evidence,
    "graph": cmd_graph,
    "graph-retrieve": cmd_graph_retrieve,
    "graphrag": cmd_graphrag,
    "graphrag-eval": cmd_graphrag_eval,
    "research": cmd_research,
    "citations": cmd_citations,
    "video": cmd_video,
    "vision": cmd_vision,
    "student": cmd_student,
    "dashboard": cmd_dashboard,
    "planner": cmd_planner,
    "rl": cmd_rl,
    "agents": cmd_agents,
    "functions": cmd_functions,
    "llm": cmd_llm,
}


def main(argv: list[str] | None = None) -> int:
    # Emit UTF-8 regardless of the console code page (Windows cp1252 otherwise
    # cannot encode Arabic text, smart quotes, arrows, etc.).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    settings = load_settings(args.config)
    return _DISPATCH[args.command](args, settings)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
