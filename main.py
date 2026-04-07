import flet as ft, asyncio, json, base64, pathlib
from dbStuff import dbAccess

def get_db(active_db):
    with open("server.json", "r") as f:
        data = json.load(f)
        dbPass = data[active_db].get("DB_PASS")
        dbIP   = data[active_db].get("DB_IP")
    return dbAccess(dbPass, dbIP)

BASE_PROFILE = {'uid': 0, 'username': ''}

profile_path = pathlib.Path("profile.json")
if not profile_path.is_file():
    json.dump(BASE_PROFILE, open("profile.json", "w"), indent=4)

pfps_dir = pathlib.Path("pfps")
pfps_dir.mkdir(exist_ok=True)
# Clear cached pfps on startup
for f in pfps_dir.glob("*.png"):
    f.unlink(missing_ok=True)

def load_profile():
    return json.load(open("profile.json", "r"))

def save_profile(data: dict):
    json.dump(data, open("profile.json", "w"), indent=4)


async def main(page: ft.Page):
    page.title    = "Chat"
    page.expand   = True
    page.theme_mode = ft.ThemeMode.DARK
    page.padding  = 0

    # ── Mobile sizing helpers ────────────────────────────────────────────────
    PFP   = 38          # avatar diameter
    FONT  = 14          # base font size
    SIDE  = 220         # sidebar width on larger screens

    db = get_db("2")

    logged_in = False

    # ── Shared file picker (one instance per page) ───────────────────────────
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    # ── Sidebar ──────────────────────────────────────────────────────────────
    friends_col = ft.Column(
        controls=[],
        scroll=ft.ScrollMode.AUTO,
        spacing=8,
        expand=True,
    )

    async def get_pfp_bytes(uid, b64_str) -> bytes:
        cache = pfps_dir / f"{uid}.png"
        if cache.is_file():
            return cache.read_bytes()
        raw = base64.b64decode(b64_str)
        cache.write_bytes(raw)
        return raw

    def avatar(pfp_bytes, size=PFP):
        return ft.Image(
            src_base64=base64.b64encode(pfp_bytes).decode(),
            width=size, height=size,
            border_radius=size / 2,
            fit=ft.ImageFit.COVER,
        )

    async def show_users():
        users = await db.get_all_users_json(db.conn)
        friends_col.controls.clear()
        friends_col.controls.append(
            ft.Text("Users", size=13, weight=ft.FontWeight.BOLD,
                    color=ft.Colors.GREY_400)
        )
        for u in users.values():
            if u["id"] == 0:
                continue
            pfp_bytes = await get_pfp_bytes(u["id"], u["pfp"])
            friends_col.controls.append(
                ft.Row(
                    controls=[
                        avatar(pfp_bytes, PFP),
                        ft.Text(u["username"], size=FONT, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=10,
                )
            )
        # Settings button at bottom
        friends_col.controls.append(ft.Divider(color=ft.Colors.GREY_700))
        friends_col.controls.append(
            ft.TextButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.SETTINGS, size=18),
                    ft.Text("Settings", size=FONT),
                ], spacing=6),
                on_click=lambda e: open_settings(),
            )
        )
        page.update()

    # ── Settings dialog ──────────────────────────────────────────────────────
    settings_username = ft.TextField(hint_text="New username", expand=True)
    settings_pfp_b64  = ft.Ref[str]()   # holds chosen b64 string
    settings_pfp_preview = ft.Image(width=PFP*2, height=PFP*2,
                                     border_radius=PFP,
                                     visible=False)

    def on_settings_pfp_picked(e: ft.FilePickerResultEvent):
        if e.files:
            raw = pathlib.Path(e.files[0].path).read_bytes()
            b64 = base64.b64encode(raw).decode()
            settings_pfp_b64.current = b64
            settings_pfp_preview.src_base64 = b64
            settings_pfp_preview.visible = True
            page.update()

    async def save_settings(e):
        uid = load_profile()["uid"]
        new_name = settings_username.value.strip() or None
        new_pfp  = getattr(settings_pfp_b64, 'current', None)
        # Clear cached pfp so it refreshes
        (pfps_dir / f"{uid}.png").unlink(missing_ok=True)
        await db.updProfile(db.conn, uid, new_name, new_pfp)
        page.pop_dialog()
        await show_users()

    def logout(e):
        nonlocal logged_in
        logged_in = False
        save_profile(BASE_PROFILE)
        message_display.controls.clear()
        page.pop_dialog()
        page.show_dialog(login_dialog)
        page.update()

    def open_settings():
        settings_username.value = ""
        settings_pfp_preview.visible = False
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Settings"),
                content=ft.Column(
                    controls=[
                        settings_pfp_preview,
                        ft.Row([
                            settings_username,
                            ft.IconButton(
                                icon=ft.Icons.PHOTO,
                                tooltip="Pick profile picture",
                                on_click=lambda e: file_picker.pick_files(
                                    allowed_extensions=["png","jpg","jpeg","webp"],
                                    on_result=on_settings_pfp_picked,
                                )
                            ),
                        ]),
                    ],
                    tight=True,
                    spacing=12,
                ),
                actions=[
                    ft.TextButton("Logout", on_click=logout),
                    ft.FilledButton("Save", on_click=save_settings),
                ],
            )
        )

    await show_users()

    # ── Auth dialogs ─────────────────────────────────────────────────────────
    auth_user  = ft.TextField(hint_text="Username", autofocus=True)
    auth_pass  = ft.TextField(hint_text="Password", password=True,
                               can_reveal_password=True)
    remember   = ft.Switch(label="Remember me")
    auth_error = ft.Text(value="", color=ft.Colors.RED_400, size=12)

    login_pfp_b64     = ft.Ref[str]()
    login_pfp_preview = ft.Image(width=PFP*2, height=PFP*2,
                                  border_radius=PFP, visible=False)

    def on_login_pfp_picked(e: ft.FilePickerResultEvent):
        if e.files:
            raw = pathlib.Path(e.files[0].path).read_bytes()
            b64 = base64.b64encode(raw).decode()
            login_pfp_b64.current = b64
            login_pfp_preview.src_base64 = b64
            login_pfp_preview.visible = True
            page.update()

    async def do_login(e):
        nonlocal logged_in
        auth_error.value = ""
        page.update()
        result = (await db.login(db.conn, auth_user.value, auth_pass.value)).split()
        if result[0] == "no":
            auth_error.value = "Incorrect username or password"
            page.update()
            return
        uid = int(result[1])
        save_profile({
            "uid": uid,
            "username": auth_user.value,
            "password": auth_pass.value,
            "remember": "yes" if remember.value else "no",
        })
        logged_in = True
        page.pop_dialog()
        await show_users()
        await load_msg_history()
        page.update()

    async def do_register(e):
        nonlocal logged_in
        auth_error.value = ""
        if not auth_user.value.strip():
            auth_error.value = "Username is required"
            page.update()
            return
        pfp_b64 = getattr(login_pfp_b64, 'current', None) or ""
        uid = await db.create_new_user(auth_user.value, auth_pass.value, pfp_b64)
        save_profile({
            "uid": int(uid),
            "username": auth_user.value,
            "password": auth_pass.value,
            "remember": "yes" if remember.value else "no",
        })
        logged_in = True
        page.pop_dialog()
        await show_users()
        await load_msg_history()
        page.update()

    # Two tabs: Login / Register
    login_tab = ft.Column(
        controls=[
            auth_user, auth_pass, remember, auth_error,
            ft.FilledButton("Login", on_click=do_login, expand=True),
        ],
        spacing=10, tight=True,
    )
    register_tab = ft.Column(
        controls=[
            auth_user, auth_pass, remember,
            ft.Row([
                login_pfp_preview,
                ft.IconButton(
                    icon=ft.Icons.PHOTO,
                    tooltip="Pick profile picture",
                    on_click=lambda e: file_picker.pick_files(
                        allowed_extensions=["png","jpg","jpeg","webp"],
                        on_result=on_login_pfp_picked,
                    )
                ),
            ]),
            auth_error,
            ft.FilledButton("Create Account", on_click=do_register, expand=True),
        ],
        spacing=10, tight=True,
    )

    auth_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=200,
        tabs=[
            ft.Tab(text="Login",    content=ft.Container(login_tab,    padding=ft.padding.only(top=12))),
            ft.Tab(text="Register", content=ft.Container(register_tab, padding=ft.padding.only(top=12))),
        ],
    )

    login_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Welcome! 👋"),
        content=ft.Container(auth_tabs, width=320, height=340),
    )

    # ── Message display ──────────────────────────────────────────────────────
    message_display = ft.Column(
        controls=[],
        scroll=ft.ScrollMode.AUTO,
        auto_scroll=True,
        expand=True,
        spacing=4,
    )

    async def add_message(message: str, uid: int, is_own: bool = False):
        users = await db.get_all_users_json(db.conn)
        pfp_bytes = b""
        for u in users.values():
            if u["id"] == uid:
                pfp_bytes = await get_pfp_bytes(uid, u["pfp"])
                break

        bubble = ft.Container(
            content=ft.Text(message, color=ft.Colors.WHITE, size=FONT,
                            selectable=True),
            bgcolor=ft.Colors.BLUE_600 if is_own else ft.Colors.GREY_700,
            border_radius=ft.border_radius.all(14),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            # Constrain bubble width so it doesn't fill the entire row
            expand=False,
        )
        av = avatar(pfp_bytes) if pfp_bytes else ft.Container(width=PFP)
        row = ft.Row(
            controls=[bubble, av] if is_own else [av, bubble],
            alignment=ft.MainAxisAlignment.END if is_own else ft.MainAxisAlignment.START,
            spacing=6,
            wrap=True,
        )
        message_display.controls.append(row)

    # ── Input row ────────────────────────────────────────────────────────────
    text_msg = ft.TextField(
        hint_text="Message…",
        border_radius=22,
        border=ft.InputBorder.OUTLINE,
        content_padding=ft.padding.symmetric(horizontal=14, vertical=10),
        expand=True,
        multiline=False,
        shift_enter=False,
        on_submit=lambda e: asyncio.create_task(send_message(e)),
    )

    async def send_message(e):
        msg = text_msg.value.strip()
        if not msg:
            return
        text_msg.value = ""
        page.update()
        uid = load_profile()["uid"]
        await add_message(f"You: {msg}", uid, is_own=True)
        page.update()
        db.write_message(uid, msg)

    send_btn = ft.IconButton(
        icon=ft.Icons.SEND_ROUNDED,
        icon_color=ft.Colors.BLUE_400,
        on_click=send_message,
    )

    input_area = ft.Container(
        content=ft.Row([text_msg, send_btn], spacing=4),
        padding=ft.padding.symmetric(horizontal=8, vertical=6),
        bgcolor=ft.Colors.GREY_900,
    )

    # ── Layout: sidebar + chat ───────────────────────────────────────────────
    sidebar = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text("capp", size=18, weight=ft.FontWeight.BOLD),
                padding=ft.padding.symmetric(horizontal=12, vertical=10),
            ),
            ft.Container(friends_col, expand=True, padding=ft.padding.symmetric(horizontal=10)),
        ], spacing=0, expand=True),
        bgcolor=ft.Colors.GREY_900,
        width=SIDE,
    )

    chat_area = ft.Container(
        content=ft.Column([
            ft.Container(message_display, expand=True,
                         padding=ft.padding.symmetric(horizontal=6, vertical=4)),
            input_area,
        ], spacing=0, expand=True),
        expand=True,
        bgcolor=ft.Colors.GREY_850,
    )

    # On narrow screens (phone portrait) hide the sidebar behind a drawer
    drawer = ft.NavigationDrawer(
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Text("capp", size=18, weight=ft.FontWeight.BOLD),
                        padding=ft.padding.only(left=12, top=12, bottom=8),
                    ),
                    friends_col,
                ], spacing=0),
                expand=True,
                padding=ft.padding.only(bottom=12),
            )
        ],
    )
    page.drawer = drawer

    menu_btn = ft.IconButton(
        icon=ft.Icons.MENU,
        on_click=lambda e: page.open_drawer(),
    )

    top_bar = ft.Container(
        content=ft.Row([
            menu_btn,
            ft.Text("Chat", size=16, weight=ft.FontWeight.BOLD, expand=True),
        ]),
        bgcolor=ft.Colors.GREY_900,
        padding=ft.padding.symmetric(horizontal=4, vertical=6),
    )

    # Full layout
    page.add(
        ft.Column([
            top_bar,
            ft.Row([
                chat_area,
            ], expand=True, spacing=0),
        ], spacing=0, expand=True)
    )

    # ── History loader ───────────────────────────────────────────────────────
    async def load_msg_history():
        total = await db.msgCount(db.conn)
        limit = min(total, 30)
        msgs  = await db.getMsg(db.conn, limit)
        my_uid = load_profile()["uid"]
        for item in reversed(msgs):
            label = f"{item['username']}: {item['content']}"
            await add_message(label, int(item["id"]), is_own=(item["id"] == my_uid))
            page.update()
        await db.lowerFlag(db.conn, my_uid)

    # ── Startup ──────────────────────────────────────────────────────────────
    prof = load_profile()
    if prof["uid"] == 0 or prof.get("remember") == "no":
        page.show_dialog(login_dialog)
    else:
        logged_in = True

    if logged_in:
        await load_msg_history()

    # ── Live update loop ─────────────────────────────────────────────────────
    while True:
        flag = await db.detFlag(db.conn, load_profile()["uid"])
        if flag and logged_in:
            my_uid   = load_profile()["uid"]
            unread   = await db.getUnread(db.conn, my_uid)
            new_msgs = await db.getMsg(db.conn, unread)
            for item in reversed(new_msgs):
                if item["id"] != my_uid:
                    label = f"{item['username']}: {item['content']}"
                    await add_message(label, int(item["id"]), is_own=False)
            await db.lowerFlag(db.conn, my_uid)
            page.update()


ft.app(target=main)
