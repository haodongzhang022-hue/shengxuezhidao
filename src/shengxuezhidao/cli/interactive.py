"""交互式问答循环(知识库二次询问)。"""


def ask_loop(asst) -> None:
    print("提示: 你可以问如'曼彻斯特大学高考要求'、'澳洲哪些大学接受高考'等。")
    while True:
        try:
            q = input("> ").strip()
        except EOFError:
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "退出"):
            break
        ans = asst.ask(q)
        print("\n" + ans.pretty + "\n")
