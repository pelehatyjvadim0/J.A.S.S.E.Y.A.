import asyncio
import uuid
from app.core.jasseya_client import JassyClient
from app.errors import AppError
from app.interfaces.cli.presenters import present_service_error, present_shutdown_message

async def main():
    session_id = str(uuid.uuid4())
    print(f'[сессия] {session_id}')
    client = JassyClient(session_id=session_id)

    while True:
        try:
            prompt = input('You: ')
            response = await client.generate_text(prompt)
            print(f'AI: {response}')
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except AppError as e:
            print(present_service_error(e))
            continue
        except Exception as e:
            print(f'[непредвиденная ошибка] {e}')
            continue


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(present_shutdown_message())