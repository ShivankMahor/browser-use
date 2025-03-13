import asyncio
from langchain_openai import ChatOpenAI
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use import Agent
import os

api_key = os.getenv("OPENAI_API_KEY")
task = os.getenv("TASK")
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set!")
if not task:
    raise ValueError("Task is not given!")

# Initialize the model
llm = ChatOpenAI(
	model='gpt-4o',
	temperature=0.0,
)

agent = Agent(task=task, llm=llm, )


async def main():
	await agent.run()


if __name__ == '__main__':
	asyncio.run(main())
