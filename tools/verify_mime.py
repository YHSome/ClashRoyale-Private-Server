import sys

sys.path.insert(0, r"C:\Users\YHSome\.codex\skills\qq-goal-email\scripts")
import send_qq_email as sq

subject = "完成汇报：双 bot 稳定运行 + 加时赛修复（修正版）"
with open(r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal\tools\update_email_3.html", "r", encoding="utf-8") as f:
    html = f.read()

body, html = sq.apply_footer(None, html)
msg = sq.build_message("949727232@qq.com", "949727232@qq.com", subject, body, html)

with open(r"C:\Users\YHSome\Projects\OtherProjects\ClashRoyal\tools\mime_dump.eml", "w", encoding="utf-8") as f:
    f.write(msg.as_string())

print("dumped")
