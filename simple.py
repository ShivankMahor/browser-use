import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use import Agent

load_dotenv()

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
task = 'Find the founders of browser-use'

agent = Agent(task=task, llm=llm, browser=browser)


async def main():
	await agent.run()


if __name__ == '__main__':
	asyncio.run(main())
