import asyncio
import win32gui
import win32process
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=False)
        page = await b.new_page()
        await page.goto("http://127.0.0.1:8088")
        await page.wait_for_timeout(3000)
        print("page url", page.url)
        cdp = await b.new_browser_cdp_session()
        info = await cdp.send("SystemInfo.getProcessInfo")
        pids = {i['id'] for i in info['processInfo'] if i['type']=='browser'}
        print('pids',pids)
        candidates=[]
        def collect(h,_):
            _,pid=win32process.GetWindowThreadProcessId(h)
            if pid in pids and win32gui.IsWindowVisible(h): candidates.append(h)
        win32gui.EnumWindows(collect,None)
        print('candidates',candidates,[win32gui.GetWindowText(h) for h in candidates])
        hwnd = candidates[0]
        print("minimize", win32gui.ShowWindow(hwnd, 6))
        await page.wait_for_timeout(1000)
        print("after min", win32gui.GetForegroundWindow(), win32gui.IsIconic(hwnd), await page.evaluate("({hidden:document.hidden,focused:document.hasFocus()})"))
        foreground = await b.new_page()
        await foreground.goto("about:blank")
        await foreground.bring_to_front()
        await page.wait_for_timeout(1000)
        print("after tab", await page.evaluate("({hidden:document.hidden,focused:document.hasFocus()})"))
        await b.close()

asyncio.run(main())
