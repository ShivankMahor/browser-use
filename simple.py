import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig

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

browser = Browser(
		config=BrowserConfig(
				# NOTE: you need to close your chrome browser - so that this can open your browser in debug mode
				# chrome_instance_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
				chrome_instance_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
		)
	)

agent = Agent(task=task, llm=llm, browser=browser)


async def main():
	await agent.run()


if __name__ == '__main__':
	asyncio.run(main())
