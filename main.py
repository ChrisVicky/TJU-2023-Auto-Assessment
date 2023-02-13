from playwright.sync_api import sync_playwright, expect
import re 
from PIL import Image
import io
from loguru import logger
import os
import configparser


def on_response(response):
    logger.trace(f'Statue {response.status}: {response.url}')


def getCaptcha(page):
    # captcha handler
    image = page.locator("id=captcha_img")
    image.screenshot(path="./tmp.png")
    logger.success("验证码已保存到 './tmp.png' 请输入验证码")
    captcha = input(">>")
    logger.info(f"captcha: {captcha}")
    return captcha


logger.add("log.log", level="TRACE")

# 获取配置文件（帐号密码）
cfgpath = "account.cfg"
config = configparser.ConfigParser()
config.read(cfgpath)
account = config.sections()[0]
userNumber = config.get(account, 'USERNAME')
passWord = config.get(account, 'PASSWORD')
headless = config.getboolean(account, 'HEADLESS')

logger.info(f"UserName: {userNumber}")
logger.info(f"PassWord: {passWord}")
logger.info(f"不使用UI: {headless}")

# 若帐号密码为空，则退出
assert userNumber is not None or passWord is not None, "帐密为空"

# tju 登录页面
url = "http://classes.tju.edu.cn"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=headless, slow_mo=50, timeout=50000)
    context = browser.new_context()
    page = context.new_page()
    page.on('response', on_response)
    # 设置弹窗选择 "是" --> 方便后续处理完成评教弹窗
    page.on("dialog", lambda dialog: dialog.accept())
    page.goto(url)

    # 处理登录
    while True:
        # 填入帐号密码
        page.get_by_label("username").fill(userNumber)
        page.get_by_label("password").fill(passWord)

        # 填入验证码
        captcha = getCaptcha(page)
        page.get_by_label("captcha").fill(captcha)
        page.locator("section", has_text="LOGIN").click()

        # 验证登录成功与否
        if page.get_by_text("Captcha Mismatch.").is_visible(timeout=1000):
            logger.warning("LOGIN FAILED!")
        else:
            logger.success("LOGIN SUCCEEDED!")
            break

    # 进入评教页面
    box = page.locator("a", has_text="量化评教").bounding_box()
    # 鼠标移动到 “量化评教” 才会出现学生评教接口
    page.mouse.move(box['x']+box['width']/2, box['y']+box['height']/2)
    page.locator("a", has_text="学生评教").click()

    page.wait_for_timeout(1000)
    # 找到每个需要进行评教的内容
    locators = page.frame_locator("id=iframeMain").locator("a", has_text="进行评教")
    logger.info(f"识别到 {locators.count()} 个 进行评教")
    cnt = locators.count()
    for i in range(cnt):
        link = locators.nth(i)
        link.click()
        name = link.text_content()
        logger.info(f"{i:2d}/{cnt:2d}: {name}")
        
        # 对每一页进行评教
        page.wait_for_timeout(1000)

        new_locators = page.frame_locator("iframe[name=\"iframeMain\"]").get_by_text("非常满意")
        logger.info(f"找到 {new_locators.count()} 个 非常满意点")
        count = new_locators.count()
        for j in range(count):
            s = new_locators.nth(j)
            s.click()

        new_locators = page.frame_locator("iframe[name=\"iframeMain\"]").get_by_text("非常同意")
        logger.info(f"找到 {new_locators.count()} 个 非常同意点")
        count = new_locators.count()
        for j in range(count):
            s = new_locators.nth(j)
            s.click()

        textarea = page.frame_locator("id=iframeMain").locator("textarea")
        logger.info(f"找到 {textarea.count()} 个 填写点: 全部填写 ‘无’")
        count = textarea.count()
        for j in range(count):
            s = textarea.nth(j)
            s.fill("无")

        page.wait_for_timeout(1000)
        page.frame_locator("id=iframeMain").get_by_role("button", name="提交").click()
        logger.info(f"Done with {name}")

    logger.info("评教完成，等待退出...")
    page.wait_for_timeout(2000)
    page.close()
    browser.close()
