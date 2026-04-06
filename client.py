import flet as ft, asyncio, json, base64, pathlib, subprocess, zlib
from dbStuff import dbAccess

def get_db(active_db):
    with open("server.json", "r") as file:
        file = json.load(file)
        dbPass = file[active_db].get("DB_PASS")
        dbIP = file[active_db].get("DB_IP")
    return dbAccess(dbPass, dbIP)

base = {
    'uid' : 0,
    'username': ''
}

if not pathlib.Path("profile.json").is_file():
    subprocess.getoutput(f"touch profile.json")
    json.dump(base, open("profile.json", "w"), indent=4)

if not pathlib.Path("pfps").is_dir():
    subprocess.getoutput("mkdir pfps")

async def main(page: ft.Page):
    page.title = "Chat app"
    page.expand = True
    page.theme_mode = ft.ThemeMode.DARK

    logged_in = False

    db = get_db("2")

    friends = ft.Column(
        controls=[],
        scroll=ft.ScrollMode.AUTO,
        margin=15
    )

    pfp_path = ft.Text("No file selected")
    user = ft.TextField(hint_text="New Username")
    async def save_settings(e):
        uid = json.load(open("profile.json", "r"))["uid"]
        username, pfp = user.value, pfp_path.value
        with open(pfp, "rb") as img_file:
            b64_string = base64.b64encode(img_file.read()).decode('utf-8')
        await db.updProfile(db.conn, uid, username, b64_string)
        subprocess.getoutput(f"rm pfps/{uid}.png")
        page.pop_dialog()
        await show_users()
        page.update()

    def logout(e):
        page.pop_dialog()
        message_display.controls.clear()
        page.show_dialog(login_dialog)

    def open_settings():
        def pick_file_kde(e):
            try:
                # Calls the native KDE file picker
                result = subprocess.run(
                    ["kdialog", "--getopenfilename", "/home", "All Files (*)"],
                    capture_output=True, text=True
                )
                file_path = result.stdout.strip()
                
                if file_path:
                    pfp_path.value = file_path
                page.update()
            except Exception as ex:
                pfp_path.value = f"Error: {ex}"
                page.update()

            settings.content.controls.append(ft.Image(src=pfp_path.value))
        settings = ft.AlertDialog(
            title="Settings",
            content=ft.Column(
                controls=[
                    user,
                    # ft.TextField(hint_text="New Password"),
                    ft.FilledButton(content="Pick PFP", on_click=pick_file_kde),
                    ft.IconButton(icon=ft.Icons.LOGOUT, on_click=logout)
                ]
            ),
            actions=ft.TextButton(content="Save", on_click=save_settings)

        )
        page.show_dialog(settings)

    async def show_users():
        users = await db.get_all_users_json(db.conn)
        friends.controls.clear()
        friends.controls.append(ft.Text("Users:"))
        for user_data in users.values():  # users is now a dict of dicts
            if user_data["id"] != 0:
                if pathlib.Path(f"pfps/{user_data["id"]}.png").is_file():
                    pfp = open(f"pfps/{user_data["id"]}.png", "rb").read()
                else:
                    pfp = base64.b64decode(user_data["pfp"])
                    open(f"pfps/{user_data["id"]}.png", "wb").write(pfp)
                size = 40
                friends.controls.append(
                    ft.Row(
                        controls=[
                            ft.Image(src=pfp, width=size, height=size, border_radius=size/2),
                            ft.Text(value=user_data["username"])
                        ],
                        spacing=15
                    )
                )
        friends.controls.append(ft.IconButton(icon=ft.Icons.SETTINGS, on_click=open_settings))
    await show_users()


    user_field = ft.TextField(hint_text="Username")
    pass_field = ft.TextField(hint_text="Password")
    pfp_path = ft.Text("No file selected")
    remember_me = ft.Switch(label="Remember me")
    def pick_file_kde(e):
        try:
            # Calls the native KDE file picker
            result = subprocess.run(
                ["kdialog", "--getopenfilename", "/home", "All Files (*)"],
                capture_output=True, text=True
            )
            file_path = result.stdout.strip()
            
            if file_path:
                pfp_path.value = file_path
            page.update()
        except Exception as ex:
            pfp_path.value = f"Error: {ex}"
            page.update()

        create_profile_dialog.content.controls.append(ft.Image(src=pfp_path.value))
    
    async def create_profile(e):
        global logged_in
        user = user_field.value
        password = pass_field.value
        pfp = pfp_path.value
        remember = "yes" if remember_me.value else "no"

        if not user:
            print("Username is required")
            return
            
        with open(pfp if pfp != "No file selected" else "temp.png", "rb") as img_file:
            b64_string = base64.b64encode(img_file.read()).decode('utf-8')
        uid = await db.create_new_user(user, password, b64_string)
        
        user_ex = {
            "uid": uid,
            "username": user,
            "password": password,
            "remember": remember
        }
        json.dump(user_ex, open("profile.json", "w"), indent=4)
        logged_in = True
        page.pop_dialog()
        page.pop_dialog()
        await show_users()
        await msg_hist()
        page.update()

    async def login():
        global logged_in
        response = (await db.login(db.conn, user_field.value, pass_field.value)).split(" ")
        remember = "yes" if remember_me.value else "no"
        match response[0]:
            case "no":
                error.value = "Incorrect login details"
                page.update()
            case "yes":
                user = user_field.value
                password = pass_field.value
                    
                user_ex = {
                    "uid": response[1],
                    "username": user,
                    "password": password,
                    "remember": remember
                }
                json.dump(user_ex, open("profile.json", "w"), indent=4)
                logged_in = True
                page.pop_dialog()
                page.pop_dialog()
                await show_users()
                await msg_hist()
                page.update()

    def show_login():
        page.show_dialog(login_dialog)

    def show_create():
        page.show_dialog(create_profile_dialog)

    error = ft.Text(value="", color=ft.Colors.RED)
    login_dialog = ft.AlertDialog(
        modal=True,
        title="Welcome!",
        content=ft.Column(
            controls=[
                user_field,
                pass_field,
                remember_me,
                error
            ]
        ),
        actions=[
            ft.TextButton(content="Create Account", on_click=show_create),
            ft.TextButton(content="Login", on_click=login)
            ]
    )

    create_profile_dialog = ft.AlertDialog(
        modal=True,
        title="Welcome!",
        content=ft.Column(
            controls=[
                user_field,
                pass_field,
                remember_me,
                ft.FilledButton(content="Pick PFP", on_click=pick_file_kde)
            ],
            expand=False
        ),
        actions=[
            ft.TextButton(content="Login", on_click=show_login),
            ft.TextButton(content="Save", on_click=create_profile)
        ]
    )

    if json.load(open("profile.json", "r"))["uid"] == 0 or json.load(open("profile.json", "r"))["remember"] == "no":
        page.show_dialog(login_dialog)
    else:
        logged_in = True

    async def sendMessage(e, id):
        if text_msg.value and text_msg.value.strip():
            msg = text_msg.value
            text_msg.value = ""
            await text_msg.focus()
            page.update()
            await add_message_to_display(f"You: {msg}", int(id), is_own=True)
            page.update()
            db.write_message(id, msg)

    async def add_message_to_display(message, uid, is_own=False):
        users = await db.get_all_users_json(db.conn)
        for user in users.values():
            if user["id"] == uid:
                if pathlib.Path(f"pfps/{uid}.png").is_file():
                    pfp = open(f"pfps/{uid}.png", "rb").read()
                else:
                    pfp = base64.b64decode(user["pfp"])
                    open(f"pfps/{uid}.png", "wb").write(pfp)

        size = 40
        message_bubble = ft.Container(
            content=ft.Text(message, color=ft.Colors.WHITE, overflow=ft.TextOverflow.CLIP),
            bgcolor=ft.Colors.BLUE_400 if is_own else ft.Colors.GREEN_400,
            border_radius=10,
            padding=10,
            margin=ft.Margin.only(bottom=5, right=20, left=20)
        )
        
        # Wrap in a Row to control positioning
        message_row = ft.Row(
            controls=[
                ft.Image(src=pfp, width=size, height=size, border_radius=size/2),
                message_bubble
                ] if not is_own else [
                message_bubble,
                ft.Image(src=pfp, width=size, height=size, border_radius=size/2)
                ],
                spacing=1,
            alignment=ft.MainAxisAlignment.END if is_own else ft.MainAxisAlignment.START,
        )
        message_display.controls.append(message_row)

    text_msg = ft.TextField(
        hint_text="Type a message...",
        border=ft.InputBorder.OUTLINE,
        expand=True,
        on_submit=lambda e: asyncio.create_task(sendMessage(e, json.load(open("profile.json", "r"))["uid"]))
    )
    send_button = ft.IconButton(
        icon=ft.Icons.SEND,
        icon_color=ft.Colors.BLUE_400,
        on_click=lambda e: asyncio.create_task(sendMessage(e, json.load(open("profile.json", "r"))["uid"]))
    )
    input_row = ft.Row(
        controls=[text_msg, send_button],
        spacing=10
    )
    message_display = ft.Column(
        controls=[],
        scroll=ft.ScrollMode.AUTO,
        auto_scroll=True,
        expand=True,
    )
    
    # Main message area with messages on top, input at bottom
    message_content = ft.Container(
        content=ft.Column(
            controls=[
                message_display,
                input_row,
            ],
            spacing=10,
            expand=True,
        ),
        bgcolor=ft.Colors.GREY_800,
        expand=True,
        padding=10,
    )

    main_content = ft.Row(
        controls=[
            ft.Container(content=friends , bgcolor=ft.Colors.GREY_900, width=400, border_radius=5),
            ft.Container(content=message_content, bgcolor=ft.Colors.GREY_800, expand=True, border_radius=5)
            ],
            expand=True
        )

    page.add(main_content)

    async def msg_hist():
        msg_count = await db.msgCount(db.conn)
        msg = await db.getMsg(db.conn, msg_count if msg_count <= 30 else 30)
        
        for item in reversed(msg):
            message = f"{item['username']}: {item['content']}"
            is_me = item["id"] == json.load(open("profile.json"))["uid"]
            await add_message_to_display(message, int(item["id"]), is_own=is_me)
            page.update()
        
        uid = json.load(open("profile.json", "r"))["uid"]
        await db.lowerFlag(db.conn, uid)

    if logged_in:
        await msg_hist()

    while await db.detFlag(db.conn, json.load(open("profile.json", "r"))["uid"]):
        if logged_in:
            unread_count = await db.getUnread(db.conn, json.load(open("profile.json", "r"))["uid"])
            msg = await db.getMsg(db.conn, unread_count)
            for item in reversed(msg):
                message = f"{item["username"]}: {item["content"]}"
                if item["id"] != json.load(open("profile.json"))["uid"]:
                    await add_message_to_display(message, int(item["id"]), is_own=False)
                await db.lowerFlag(db.conn, json.load(open("profile.json", "r"))["uid"])
                page.update()

# Run the app
ft.run(main)