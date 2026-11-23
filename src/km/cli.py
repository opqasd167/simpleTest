import argparse

from km.config import get_settings
from km.container import build_indexer, build_qa_service
from km.logging_setup import setup_logging
from km.observability import flush
from km.question_log import log_question
from km.storage.sql_store import SqlStore


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(prog="km")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="create SQLite tables and demo rows")
    sub.add_parser("ingest", help="index files in data/raw/docs")
    ask = sub.add_parser("ask", help="ask one question")
    ask.add_argument("question")
    serve = sub.add_parser("serve", help="start the REST API and the chat UI")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    s = get_settings()
    if args.cmd == "seed":
        SqlStore(s.sqlite_path).init_from_script(s.seed_sql)
        print("Database ready")
    elif args.cmd == "ingest":
        print(f"Indexed {build_indexer(s).index_folder(s.docs_dir)} chunks")
    elif args.cmd == "ask":
        result = build_qa_service(s).ask(args.question)
        log_question(s.question_log, result, channel="cli")
        print(result.model_dump_json(indent=2))
        flush()  # send the trace to Langfuse before exiting
    elif args.cmd == "serve":
        import uvicorn
        print(f"Chat UI: http://127.0.0.1:{args.port}/ui    API docs: http://127.0.0.1:{args.port}/docs")
        uvicorn.run("km.api.app:app", port=args.port)


if __name__ == "__main__":
    main()
