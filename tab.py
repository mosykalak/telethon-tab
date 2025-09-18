import asyncio
import json
import os
from datetime import datetime
from typing import List, Set
from telethon import TelegramClient, events, Button
from telethon.tl.types import Channel, Chat, User
from telethon.errors import FloodWaitError, ChatWriteForbiddenError
import logging

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PersonalBroadcaster:
    def __init__(self, api_id: int, api_hash: str, phone: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.client = TelegramClient(f'session_{phone}', api_id, api_hash)
        self.data_file = 'broadcaster_data.json'
        self.load_data()
        self.broadcast_task = None
        self.forward_replies = True  # افزودن تنظیم جدید برای فوروارد ریپلای‌ها

    def load_data(self):
        """بارگذاری تنظیمات از فایل"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.message = data.get('message', '📢 پیام پیش‌فرض')
            self.interval_minutes = data.get('interval', 10)
            self.excluded_groups = set(data.get('excluded_groups', []))
            self.is_active = data.get('is_active', False)
            self.include_channels = data.get('include_channels', False)
            self.forward_replies = data.get('forward_replies', True)  # بارگذاری تنظیم جدید
        except FileNotFoundError:
            self.message = '📢 پیام پیش‌فرض'
            self.interval_minutes = 10
            self.excluded_groups = set()
            self.is_active = False
            self.include_channels = False
            self.forward_replies = True  # مقدار پیش‌فرض
            self.save_data()

    def save_data(self):
        """ذخیره تنظیمات در فایل"""
        data = {
            'message': self.message,
            'interval': self.interval_minutes,
            'excluded_groups': list(self.excluded_groups),
            'is_active': self.is_active,
            'include_channels': self.include_channels,
            'forward_replies': self.forward_replies  # ذخیره تنظیم جدید
        }
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def get_all_groups(self) -> List:
        """دریافت لیست تمام گروه‌ها و کانال‌ها"""
        dialogs = await self.client.get_dialogs()
        groups = []
        for dialog in dialogs:
            entity = dialog.entity
            # فقط گروه‌ها و سوپرگروه‌ها
            if isinstance(entity, (Chat, Channel)):
                if isinstance(entity, Channel):
                    # بررسی اینکه کانال است یا سوپرگروه
                    if entity.megagroup:  # سوپرگروه
                        groups.append(entity)
                    elif self.include_channels and entity.broadcast:  # کانال
                        groups.append(entity)
                else:
                    # گروه معمولی
                    groups.append(entity)
        return groups

    async def broadcast_message(self):
        """ارسال پیام به همه گروه‌ها"""
        while self.is_active:
            try:
                groups = await self.get_all_groups()
                success_count = 0
                failed_count = 0

                await self.client.send_message('me', f"🚀 شروع ارسال به {len(groups)} گروه/کانال...")

                for group in groups:
                    if str(group.id) not in self.excluded_groups:
                        try:
                            await self.client.send_message(group.id, self.message)
                            success_count += 1
                            await asyncio.sleep(2)  # تاخیر برای جلوگیری از محدودیت
                        except FloodWaitError as e:
                            logger.warning(f"محدودیت زمانی: {e.seconds} ثانیه")
                            await asyncio.sleep(e.seconds)
                        except ChatWriteForbiddenError:
                            logger.error(f"عدم دسترسی ارسال به: {group.title}")
                            failed_count += 1
                        except Exception as e:
                            logger.error(f"خطا در ارسال به {group.title}: {e}")
                            failed_count += 1

                # گزارش نتیجه
                await self.client.send_message('me', f"✅ ارسال کامل شد!\n"
                                               f"موفق: {success_count}\n"
                                               f"ناموفق: {failed_count}")

                # انتظار تا ارسال بعدی
                await asyncio.sleep(self.interval_minutes * 60)
            except Exception as e:
                logger.error(f"خطا در broadcast: {e}")
                await asyncio.sleep(60)

    async def show_main_menu(self):
        """نمایش منوی اصلی در Saved Messages"""
        buttons = [
            [Button.inline('📝 تغییر پیام', 'set_message')],
            [Button.inline('⏰ تغییر زمان ارسال', 'set_interval')],
            [Button.inline('➕ اضافه کردن گروه مستثنی', 'add_exclude'), 
             Button.inline('➖ حذف گروه مستثنی', 'remove_exclude')],
            [Button.inline('📋 لیست گروه‌های مستثنی', 'list_exclude')],
            [Button.inline('🧪 تست ارسال', 'test_send')],
            [Button.inline('📊 وضعیت', 'status')],
            [Button.inline('🔔 فوروارد ریپلای‌ها' if not self.forward_replies else '🔕 قطع فوروارد ریپلای‌ها', 'toggle_forward_replies')],
            [Button.inline('▶️ شروع ارسال' if not self.is_active else '⏸️ توقف ارسال', 'toggle_broadcast')],
            [Button.inline('🔰 شروع', 'start'), Button.inline('🔄 بازخوانی منو', 'refresh')]
        ]

        status_emoji = '✅' if self.is_active else '❌'
        forward_emoji = '✅' if self.forward_replies else '❌'
        message = f"""
🤖 **پنل کنترل پیام‌رسان شخصی**

📝 **پیام فعلی:** {self.message}
⏰ **فاصله ارسال:** هر {self.interval_minutes} دقیقه
🚫 **گروه‌های مستثنی:** {len(self.excluded_groups)} گروه
📡 **وضعیت ارسال:** {status_emoji} {'فعال' if self.is_active else 'غیرفعال'}
🔔 **فوروارد ریپلای‌ها:** {forward_emoji} {'فعال' if self.forward_replies else 'غیرفعال'}

لطفاً یک گزینه را انتخاب کنید:
"""
        await self.client.send_message('me', message, buttons=buttons)

    async def handle_replied_messages(self, event):
        """مدیریت پیام‌هایی که به اکانت ریپلای شده‌اند"""
        if not self.forward_replies:
            return

        # بررسی اینکه پیام ریپلای است و به اکانت ما ریپلای شده
        if event.is_reply:
            try:
                replied_message = await event.get_reply_message()
                # بررسی اینکه آیا ریپلای به یکی از پیام‌های ماست
                if replied_message and replied_message.sender_id == (await self.client.get_me()).id:
                    # دریافت اطلاعات چت و کاربر
                    chat = await event.get_chat()
                    sender = await event.get_sender()

                    # ایجاد متن برای فوروارد
                    forward_text = f"""
🔔 **ریپلای جدید دریافت شد!**

👤 **ارسال کننده:** {sender.first_name} {getattr(sender, 'last_name', '') or ''} (@{getattr(sender, 'username', 'ندارد')})
💬 **چت:** {getattr(chat, 'title', 'چت خصوصی')}
🆔 **آیدی چت:** `{chat.id}`
📝 **پیام:** {event.message.message}

📎 **پیام اصلی:** {replied_message.message}
                    """

                    # فوروارد به Saved Messages
                    await self.client.send_message('me', forward_text)
                    logger.info(f"ریپلای جدید از {sender.first_name} در چت {getattr(chat, 'title', 'خصوصی')} فوروارد شد")

            except Exception as e:
                logger.error(f"خطا در پردازش ریپلای: {e}")

    async def handle_commands(self, event):
        """مدیریت دستورات در Saved Messages"""
        if event.chat_id != (await self.client.get_me()).id:
            # اگر پیام از چت دیگری است، بررسی کن آیا ریپلای به اکانت ماست
            await self.handle_replied_messages(event)
            return

        message = event.message.message.lower()

        # دستورات اصلی
        if message == '/start' or message == '/menu':
            await self.show_main_menu()
        elif message == '/toggle':  # دستور جدید برای تغییر وضعیت
            self.is_active = not self.is_active
            self.save_data()

            if self.is_active:
                self.broadcast_task = asyncio.create_task(self.broadcast_message())
                await event.reply("✅ ارسال خودکار فعال شد!")
            else:
                if self.broadcast_task:
                    self.broadcast_task.cancel()
                await event.reply("⏸️ ارسال خودکار متوقف شد!")

            await self.show_main_menu()
        elif message == '/toggle_forward':  # دستور جدید برای تغییر وضعیت فوروارد ریپلای‌ها
            self.forward_replies = not self.forward_replies
            self.save_data()

            if self.forward_replies:
                await event.reply("✅ فوروارد ریپلای‌ها فعال شد!")
            else:
                await event.reply("🔕 فوروارد ریپلای‌ها غیرفعال شد!")

            await self.show_main_menu()
        elif message.startswith('/setmsg '):
            new_message = event.message.message[8:]
            self.message = new_message
            self.save_data()
            await event.reply(f"✅ پیام جدید ذخیره شد:\n{new_message}")
            await self.show_main_menu()
        elif message.startswith('/settime '):
            try:
                minutes = int(message.split()[1])
                if minutes < 1:
                    await event.reply("❌ زمان باید حداقل 1 دقیقه باشد!")
                    return
                self.interval_minutes = minutes
                self.save_data()
                # اگر در حال ارسال است، تسک را ریستارت کن
                if self.is_active and self.broadcast_task:
                    self.broadcast_task.cancel()
                    self.broadcast_task = asyncio.create_task(self.broadcast_message())
                await event.reply(f"✅ زمان ارسال به {minutes} دقیقه تغییر کرد!")
                await self.show_main_menu()
            except (ValueError, IndexError):
                await event.reply("❌ فرمت صحیح: /settime [دقیقه]\nمثال: /settime 30")
        elif message.startswith('/exclude '):
            try:
                group_id = message.split()[1]
                self.excluded_groups.add(group_id)
                self.save_data()
                await event.reply(f"✅ گروه {group_id} به لیست مستثنی اضافه شد!")
            except IndexError:
                await event.reply("❌ فرمت صحیح: /exclude [آیدی گروه]")
        elif message.startswith('/include '):
            try:
                group_id = message.split()[1]
                if group_id in self.excluded_groups:
                    self.excluded_groups.remove(group_id)
                    self.save_data()
                    await event.reply(f"✅ گروه {group_id} از لیست مستثنی حذف شد!")
                else:
                    await event.reply(f"❌ گروه {group_id} در لیست مستثنی نیست!")
            except IndexError:
                await event.reply("❌ فرمت صحیح: /include [آیدی گروه]")
        elif message == '/list':
            groups = await self.get_all_groups()
            text = "📋 **لیست گروه‌ها:**\n\n"
            for i, group in enumerate(groups, 1):
                excluded = "🚫" if str(group.id) in self.excluded_groups else "✅"
                text += f"{i}. {excluded} {group.title}\n 🆔 `{group.id}`\n\n"
                if i % 10 == 0:  # هر 10 گروه در یک پیام
                    await event.reply(text)
                    text = ""
            if text:
                await event.reply(text)
        elif message == '/help':
            help_text = """
📚 **راهنمای دستورات:**

🔹 `/start` یا `/menu` - نمایش منوی اصلی
🔹 `/toggle` - تغییر وضعیت ارسال (فعال/غیرفعال)
🔹 `/toggle_forward` - تغییر وضعیت فوروارد ریپلای‌ها
🔹 `/setmsg [پیام]` - تنظیم پیام ارسالی
🔹 `/settime [دقیقه]` - تنظیم فاصله زمانی
🔹 `/exclude [آیدی]` - اضافه کردن به مستثنی‌ها
🔹 `/include [آیدی]` - حذف از مستثنی‌ها
🔹 `/list` - نمایش لیست همه گروه‌ها
🔹 `/test` - تست ارسال پیام
🔹 `/status` - وضعیت فعلی
🔹 `/help` - این راهنما

💡 **نکات:**
• آیدی گروه‌ها را می‌توانید از دستور /list بگیرید
• برای پیام‌های چند خطی از /setmsg استفاده کنید
• حداقل زمان ارسال 1 دقیقه است
• وقتی فوروارد ریپلای‌ها فعال است، هر ریپلای به اکانت شما در Saved Messages فوروارد می‌شود
"""
            await event.reply(help_text)
        elif message == '/test':
            await event.reply("🧪 در حال تست ارسال...")
            groups = await self.get_all_groups()
            test_groups = [g for g in groups if str(g.id) not in self.excluded_groups][:3]
            for group in test_groups:
                try:
                    await self.client.send_message(group.id, f"🧪 تست: {self.message}")
                    await event.reply(f"✅ ارسال به {group.title} موفق بود")
                except Exception as e:
                    await event.reply(f"❌ خطا در ارسال به {group.title}: {e}")
                await asyncio.sleep(2)
        elif message == '/status':
            groups = await self.get_all_groups()
            active_groups = len([g for g in groups if str(g.id) not in self.excluded_groups])
            status_text = f"""
📊 **وضعیت سیستم:**

📡 وضعیت ارسال: {'✅ فعال' if self.is_active else '❌ غیرفعال'}
🔔 فوروارد ریپلای‌ها: {'✅ فعال' if self.forward_replies else '❌ غیرفعال'}
⏰ فاصله ارسال: هر {self.interval_minutes} دقیقه
👥 کل گروه‌ها: {len(groups)}
✅ گروه‌های فعال: {active_groups}
🚫 گروه‌های مستثنی: {len(self.excluded_groups)}
📝 پیام: {self.message}
"""
            await event.reply(status_text)

    async def handle_callback(self, event):
        """مدیریت دکمه‌های inline"""
        data = event.data.decode('utf-8')

        if data == 'toggle_broadcast':
            self.is_active = not self.is_active
            self.save_data()
            if self.is_active:
                self.broadcast_task = asyncio.create_task(self.broadcast_message())
                await event.edit("✅ ارسال خودکار فعال شد!")
            else:
                if self.broadcast_task:
                    self.broadcast_task.cancel()
                await event.edit("⏸️ ارسال خودکار متوقف شد!")
            await asyncio.sleep(2)
            await self.show_main_menu()
        elif data == 'toggle_forward_replies':  # مدیریت دکمه تغییر وضعیت فوروارد ریپلای‌ها
            self.forward_replies = not self.forward_replies
            self.save_data()
            if self.forward_replies:
                await event.edit("✅ فوروارد ریپلای‌ها فعال شد!")
            else:
                await event.edit("🔕 فوروارد ریپلای‌ها غیرفعال شد!")
            await asyncio.sleep(2)
            await self.show_main_menu()
        elif data == 'set_message':
            await event.edit(
                "📝 پیام جدید را ارسال کنید:\n"
                "فرمت: `/setmsg [پیام شما]`\n\n"
                "مثال:\n`/setmsg سلام دوستان عزیز`"
            )
        elif data == 'set_interval':
            await event.edit(
                "⏰ زمان جدید را به دقیقه ارسال کنید:\n"
                "فرمت: `/settime [دقیقه]`\n\n"
                "مثال:\n`/settime 30`"
            )
        elif data == 'add_exclude':
            await event.edit(
                "➕ آیدی گروه مورد نظر را ارسال کنید:\n"
                "فرمت: `/exclude [آیدی]`\n\n"
                "برای دیدن آیدی گروه‌ها از `/list` استفاده کنید"
            )
        elif data == 'remove_exclude':
            if not self.excluded_groups:
                await event.edit("❌ لیست مستثنی‌ها خالی است!")
                await asyncio.sleep(2)
                await self.show_main_menu()
                return
            text = "➖ گروه‌های مستثنی:\n\n"
            for group_id in self.excluded_groups:
                text += f"🆔 `{group_id}`\n"
            text += "\nبرای حذف: `/include [آیدی]`"
            await event.edit(text)
        elif data == 'list_exclude':
            if not self.excluded_groups:
                await event.edit("📋 هیچ گروه مستثنی وجود ندارد!")
            else:
                text = "📋 **گروه‌های مستثنی:**\n\n"
                groups = await self.get_all_groups()
                for group_id in self.excluded_groups:
                    group_name = "نامشخص"
                    for g in groups:
                        if str(g.id) == group_id:
                            group_name = g.title
                            break
                    text += f"• {group_name}\n 🆔 `{group_id}`\n\n"
                await event.edit(text)
            await asyncio.sleep(3)
            await self.show_main_menu()
        elif data == 'test_send':
            await event.edit("🧪 در حال تست ارسال به 3 گروه اول...")
            groups = await self.get_all_groups()
            test_groups = [g for g in groups if str(g.id) not in self.excluded_groups][:3]
            if not test_groups:
                await event.edit("❌ هیچ گروه فعالی برای تست وجود ندارد!")
                await asyncio.sleep(2)
                await self.show_main_menu()
                return
            result = "🧪 **نتیجه تست:**\n\n"
            for group in test_groups:
                try:
                    await self.client.send_message(group.id, f"🧪 تست: {self.message}")
                    result += f"✅ {group.title}\n"
                except Exception as e:
                    result += f"❌ {group.title}: {str(e)[:30]}\n"
                await asyncio.sleep(2)
            await event.edit(result)
            await asyncio.sleep(3)
            await self.show_main_menu()
        elif data == 'status':
            groups = await self.get_all_groups()
            active_groups = len([g for g in groups if str(g.id) not in self.excluded_groups])
            status_text = f"""
📊 **وضعیت سیستم:**

📡 وضعیت: {'✅ فعال' if self.is_active else '❌ غیرفعال'}
🔔 فوروارد ریپلای‌ها: {'✅ فعال' if self.forward_replies else '❌ غیرفعال'}
⏰ فاصله ارسال: هر {self.interval_minutes} دقیقه
👥 کل گروه‌ها: {len(groups)}
✅ گروه‌های فعال: {active_groups}
🚫 گروه‌های مستثنی: {len(self.excluded_groups)}
📝 پیام فعلی: {self.message}
"""
            await event.edit(status_text)
            await asyncio.sleep(5)
            await self.show_main_menu()
        elif data == 'refresh':
            await event.delete()
            await self.show_main_menu()
        elif data == 'start':  # مدیریت دکمه شروع
            await event.delete()
            await self.show_main_menu()

    async def run(self):
        """اجرای اصلی برنامه"""
        await self.client.start(phone=self.phone)

        # ثبت event handlers
        self.client.add_event_handler(
            self.handle_commands, events.NewMessage()
        )
        self.client.add_event_handler(
            self.handle_callback, events.CallbackQuery()
        )

        print("✅ برنامه آماده است!")
        print("برای شروع در Saved Messages خود دستور /start را بفرستید")

        # ارسال پیام خوشآمدگویی با دکمه شروع
        await self.client.send_message(
            'me',
            "🤖 ربات پیام‌رسان شخصی آماده است!\n\n"
            "🔔 **قابلیت جدید:** اگر کسی در هر چتی به اکانت شما ریپلای کند، پیامش به صورت خودکار به اینجا فوروارد می‌شود.\n\n"
            "برای نمایش منوی اصلی از دکمه زیر استفاده کنید:",
            buttons=[[Button.inline('🔰 شروع', 'start')]]
        )

        # اگر قبلاً فعال بوده، ارسال را شروع کن
        if self.is_active:
            self.broadcast_task = asyncio.create_task(self.broadcast_message())

        await self.client.run_until_disconnected()

# حذف تابع main و بلوک if __name__ و جایگزینی با تابع run_bot
async def run_bot():
    # اطلاعات حساب خود را اینجا وارد کنید
    API_ID = 23853619  # از my.telegram.org دریافت کنید
    API_HASH = "098dc6e71f2e099dff99b16629f28bce"  # از my.telegram.org دریافت کنید
    PHONE = "+989906365257"  # شماره تلفن با کد کشور

    broadcaster = PersonalBroadcaster(API_ID, API_HASH, PHONE)
    await broadcaster.run()
