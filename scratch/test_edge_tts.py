import asyncio
import edge_tts

async def test_voice(text, voice):
    print(f"\nProbando voz: {voice} con texto: '{text}'")
    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    async for chunk in communicate.stream():
        if chunk["type"] != "audio":
            print(f"EVENTO: {chunk}")

async def main():
    await test_voice("Hello world", "en-US-GuyNeural")
    await test_voice("había una vez un cazador", "es-ES-AlvaroNeural")

if __name__ == "__main__":
    asyncio.run(main())
