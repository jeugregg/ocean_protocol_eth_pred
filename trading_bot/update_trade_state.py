import asyncio
import json

from main_bot import run_sync_only


async def main():
    result = await run_sync_only()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())