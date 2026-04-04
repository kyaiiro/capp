import flet as ft, asyncio, json, base64, pathlib, subprocess
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

    users = await db.get_all_users_json(db.conn)

    friends = ft.Column(
        controls=[ft.Text("Users:")],
        scroll=ft.ScrollMode.AUTO,
        margin=15
    )

    def show_users():
        friends.controls.clear()
        for user_data in users.values():  # users is now a dict of dicts
            if user_data["id"] != 0:
                pfp = base64.b64decode(user_data.get("pfp"))
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
    show_users()


    user_field = ft.TextField(hint_text="Username")
    pass_field = ft.TextField(hint_text="Password")
    
    async def create_profile(e):
        user = user_field.value
        password = pass_field.value
        
        if not user:
            print("Username is required")
            return
            
        with open("temp1.png", "rb") as img_file:
            b64_string = base64.b64encode(img_file.read()).decode('utf-8')
        uid = await db.create_new_user(user, password, b64_string)
        
        user_ex = {
            "uid": uid,
            "username": user,
            "password": password
        }
        json.dump(user_ex, open("profile.json", "w"), indent=4)
        show_users()
        page.pop_dialog()
        page.pop_dialog()
        await msg_hist()
        page.update()

    async def login():
        response = (await db.login(db.conn, user_field.value, pass_field.value)).split(" ")
        match response[0]:
            case "no":
                print("Incorrect")
            case "yes":
                user = user_field.value
                password = pass_field.value
                    
                user_ex = {
                    "uid": response[1],
                    "username": user
                }
                json.dump(user_ex, open("profile.json", "w"), indent=4)
                page.pop_dialog()
                page.pop_dialog()
                show_users()
                await msg_hist()
                page.update()

    login_dialog = ft.AlertDialog(
        modal=True,
        title="Welcome!",
        content=ft.Column(
            controls=[
                user_field,
                pass_field,
                ft.Text(value="")
            ]
        ),
        actions=[
                ft.TextButton(content="Login", on_click=login)
            ]
    )

    create_profile_dialog = ft.AlertDialog(
        modal=True,
        title="Welcome!",
        content=ft.Column(
            controls=[
                user_field,
                pass_field
            ],
            expand=False
        ),
        actions=[
            ft.TextButton(content="Save", on_click=create_profile)
        ]
    )

    def show_login():
        page.show_dialog(login_dialog)

    def show_create():
        page.show_dialog(create_profile_dialog)
    
    first_start = ft.AlertDialog(
        modal=True,
        title="Welcome!",
        content=ft.Column(
            controls=[
                ft.FilledButton(content="Login", on_click=show_login),
                ft.FilledButton(content="Create User", on_click=show_create)
            ]
        )
    )

    if json.load(open("profile.json", "r"))["uid"] == 0:
        page.show_dialog(first_start)
    else:
        logged_in = True

    async def sendMessage(e, id):
        if text_msg.value and text_msg.value.strip():
            msg = text_msg.value
            text_msg.value = ""
            await add_message_to_display(f"You: {msg}", int(id), is_own=True)
            page.update()  # Clear the text field immediately
            db.write_message(id, msg)
            await text_msg.focus()

    async def add_message_to_display(message, uid, is_own=False):
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
            ft.Container(content=friends, bgcolor=ft.Colors.GREY_900, width=400, border_radius=5),
            ft.Container(content=message_content, bgcolor=ft.Colors.GREY_800, expand=True, border_radius=5)
            ],
            expand=True
        )

    page.add(main_content)

    async def msg_hist():
        msg_count = await db.msgCount(db.conn)
        msg = await db.getMsg(db.conn, msg_count if msg_count <= 30 else 30)
        for item in reversed(msg):
            message = f"{item["username"]}: {item["content"]}"
            await add_message_to_display(message, int(item["id"]), is_own=True if item["username"] == json.load(open("profile.json"))["username"] else False)
            page.update()
            await db.lowerFlag(db.conn, json.load(open("profile.json", "r"))["uid"])

    if logged_in:
        await msg_hist()

    while await db.detFlag(db.conn, json.load(open("profile.json", "r"))["uid"]):
        unread_count = await db.getUnread(db.conn, json.load(open("profile.json", "r"))["uid"])
        msg = await db.getMsg(db.conn, unread_count)
        for item in reversed(msg):
            message = f"{item["username"]}: {item["content"]}"
            await add_message_to_display(message, int(item["id"]), is_own=False)
            page.update()
            await db.lowerFlag(db.conn, json.load(open("profile.json", "r"))["uid"])

# Run the app
ft.run(main)