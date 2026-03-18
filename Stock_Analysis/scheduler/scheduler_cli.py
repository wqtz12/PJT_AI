#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Stock Analysis Scheduler CLI
  - 스케줄러 상태 확인, 수동 실행, 워치리스트 관리
═══════════════════════════════════════════════════════════════

Usage:
  python scheduler_cli.py status          # 스케줄러 상태 확인
  python scheduler_cli.py list            # 워치리스트 목록
  python scheduler_cli.py run <watchlist> # 수동 분석 실행
  python scheduler_cli.py add <watchlist> <ticker>  # 종목 추가
  python scheduler_cli.py remove <watchlist> <ticker>  # 종목 제거
  python scheduler_cli.py install         # launchd 에이전트 설치
  python scheduler_cli.py uninstall       # launchd 에이전트 제거
  python scheduler_cli.py history         # 최근 이력 조회
"""
import sys
import os
import argparse
import json

# API 기본 주소
API_BASE = "http://127.0.0.1:8500/api"


def _api_call(method, path, data=None):
    """API 호출 헬퍼"""
    try:
        import requests
    except ImportError:
        try:
            import httpx as requests
        except ImportError:
            print("Error: 'requests' or 'httpx' package required.")
            print("  pip install httpx")
            sys.exit(1)

    url = f"{API_BASE}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10)
        elif method == "POST":
            resp = requests.post(url, json=data, timeout=30)
        elif method == "PUT":
            resp = requests.put(url, json=data, timeout=10)
        elif method == "DELETE":
            resp = requests.delete(url, timeout=10)
        else:
            raise ValueError(f"Unknown method: {method}")

        if hasattr(resp, 'json'):
            return resp.json() if callable(resp.json) else resp.json
        return json.loads(resp.text)
    except Exception as e:
        if "Connection refused" in str(e) or "ConnectError" in str(e):
            print("Error: Scheduler is not running.")
            print("  Start with: python scheduler/scheduler_runner.py")
            print("  Or install: python scheduler/scheduler_cli.py install")
        else:
            print(f"Error: {e}")
        sys.exit(1)


def cmd_status(args):
    """스케줄러 상태 확인"""
    data = _api_call("GET", "/status")
    print(f"\n{'='*50}")
    print(f"  Stock Analysis Scheduler Status")
    print(f"{'='*50}\n")

    running = data.get("running", False)
    print(f"  Status: {'Running' if running else 'Stopped'}")

    # 통계
    stats = data.get("stats", {})
    print(f"  Total Runs: {stats.get('total_batch_runs', 0)}")
    print(f"  Today: {stats.get('today_runs', 0)}")
    print(f"  Success Rate: {stats.get('success_rate', 0)}%\n")

    # 등록된 작업
    jobs = data.get("jobs", [])
    if jobs:
        print("  Scheduled Jobs:")
        for job in jobs:
            print(f"    - {job['name']}: next at {job['next_run']}")
    else:
        print("  No scheduled jobs.")

    # 현재 실행 중인 작업
    current = data.get("current_jobs", {})
    if current:
        print("\n  Current Jobs:")
        for name, info in current.items():
            print(f"    - {name}: {info.get('status', 'unknown')}")

    print()


def cmd_list(args):
    """워치리스트 목록"""
    data = _api_call("GET", "/watchlists")
    print(f"\n{'='*60}")
    print(f"  Watchlists")
    print(f"{'='*60}\n")

    if not data:
        print("  No watchlists configured.\n")
        return

    for name, wl in data.items():
        enabled = wl.get("enabled", True)
        status = "ON" if enabled else "OFF"
        tickers = ", ".join(wl.get("tickers", []))
        schedule = wl.get("schedule", "N/A")
        atype = wl.get("analysis_type", "full")
        notifs = ", ".join(wl.get("notifications", []))

        print(f"  [{status}] {name}")
        print(f"       Tickers:  {tickers}")
        print(f"       Schedule: {schedule} KST")
        print(f"       Type:     {atype}")
        print(f"       Notify:   {notifs}")
        print()


def cmd_run(args):
    """수동 분석 실행"""
    watchlist = args.watchlist
    print(f"Triggering analysis for '{watchlist}'...")
    data = _api_call("POST", f"/run/{watchlist}")

    if "error" in data:
        print(f"Error: {data['error']}")
    else:
        tickers = data.get("tickers", [])
        print(f"Started! ({len(tickers)} tickers: {', '.join(tickers)})")
        print(f"Check progress at http://127.0.0.1:8500")


def cmd_add(args):
    """종목 추가"""
    watchlist = args.watchlist
    ticker = args.ticker.upper()

    # 현재 워치리스트 가져오기
    data = _api_call("GET", "/watchlists")
    if watchlist not in data:
        print(f"Error: Watchlist '{watchlist}' not found.")
        print(f"Available: {', '.join(data.keys())}")
        return

    wl = data[watchlist]
    tickers = wl.get("tickers", [])

    if ticker in tickers:
        print(f"'{ticker}' is already in '{watchlist}'.")
        return

    tickers.append(ticker)
    _api_call("PUT", f"/watchlists/{watchlist}", {"tickers": tickers})
    print(f"Added '{ticker}' to '{watchlist}'. ({len(tickers)} tickers)")


def cmd_remove(args):
    """종목 제거"""
    watchlist = args.watchlist
    ticker = args.ticker.upper()

    data = _api_call("GET", "/watchlists")
    if watchlist not in data:
        print(f"Error: Watchlist '{watchlist}' not found.")
        return

    wl = data[watchlist]
    tickers = wl.get("tickers", [])

    if ticker not in tickers:
        print(f"'{ticker}' is not in '{watchlist}'.")
        return

    tickers.remove(ticker)
    _api_call("PUT", f"/watchlists/{watchlist}", {"tickers": tickers})
    print(f"Removed '{ticker}' from '{watchlist}'. ({len(tickers)} tickers remaining)")


def cmd_history(args):
    """최근 이력"""
    data = _api_call("GET", "/history?limit=10")
    history = data.get("history", [])

    print(f"\n{'='*70}")
    print(f"  Recent Analysis History")
    print(f"{'='*70}\n")

    if not history:
        print("  No history yet.\n")
        return

    print(f"  {'Time':<18} {'Watchlist':<15} {'Tickers':>7} {'OK':>4} {'Fail':>4} {'Duration':>10}")
    print(f"  {'-'*18} {'-'*15} {'-'*7} {'-'*4} {'-'*4} {'-'*10}")

    for run in history:
        ts = run.get("timestamp", "")[:16]
        wl = run.get("watchlist_name", "")
        total = run.get("total_tickers", 0)
        ok = run.get("success_count", 0)
        fail = run.get("fail_count", 0)
        dur = f"{run.get('total_duration_sec', 0):.1f}s"
        print(f"  {ts:<18} {wl:<15} {total:>7} {ok:>4} {fail:>4} {dur:>10}")

    print()


def cmd_install(args):
    """launchd 에이전트 설치"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "launchd", "install_scheduler.sh")
    if not os.path.exists(script):
        print(f"Error: Install script not found: {script}")
        sys.exit(1)

    import subprocess
    subprocess.run(["bash", script], check=True)


def cmd_uninstall(args):
    """launchd 에이전트 제거"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "launchd", "uninstall_scheduler.sh")
    if not os.path.exists(script):
        print(f"Error: Uninstall script not found: {script}")
        sys.exit(1)

    import subprocess
    subprocess.run(["bash", script], check=True)


def main():
    parser = argparse.ArgumentParser(
        description="Stock Analysis Scheduler CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                  Show scheduler status
  %(prog)s list                    List all watchlists
  %(prog)s run bigtech             Run bigtech watchlist now
  %(prog)s add bigtech TSLA        Add TSLA to bigtech
  %(prog)s remove bigtech META     Remove META from bigtech
  %(prog)s history                 Show recent history
  %(prog)s install                 Install as macOS service
  %(prog)s uninstall               Remove macOS service
""")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    subparsers.add_parser("status", help="Show scheduler status")
    subparsers.add_parser("list", help="List all watchlists")

    run_p = subparsers.add_parser("run", help="Manual analysis run")
    run_p.add_argument("watchlist", help="Watchlist name")

    add_p = subparsers.add_parser("add", help="Add ticker to watchlist")
    add_p.add_argument("watchlist", help="Watchlist name")
    add_p.add_argument("ticker", help="Ticker symbol (e.g., AAPL)")

    rem_p = subparsers.add_parser("remove", help="Remove ticker from watchlist")
    rem_p.add_argument("watchlist", help="Watchlist name")
    rem_p.add_argument("ticker", help="Ticker symbol")

    subparsers.add_parser("history", help="Show recent analysis history")
    subparsers.add_parser("install", help="Install launchd agent")
    subparsers.add_parser("uninstall", help="Uninstall launchd agent")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cmd_map = {
        "status": cmd_status,
        "list": cmd_list,
        "run": cmd_run,
        "add": cmd_add,
        "remove": cmd_remove,
        "history": cmd_history,
        "install": cmd_install,
        "uninstall": cmd_uninstall,
    }

    cmd_func = cmd_map.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
