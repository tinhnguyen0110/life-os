# Teammate Orphan / Comms Playbook — life-os team

> Khi agent (teammate) "nhận message được nhưng không reply về", hoặc TeamDelete kẹt.
> Đúc kết từ sự cố 2026-06-14: `docker stop docker` khẩn + host overload (load 188) giết các tmux pane của agent giữa chừng → registry vẫn ghi "active" → orphan.

---

## 1. Triệu chứng (nhận ra orphan)

- `SendMessage` tới agent trả **success** (message ghi vào inbox) NHƯNG agent **không reply về** sau >2-3 phút.
- HOẶC `TeamDelete` báo: `Cannot cleanup team with N active member(s): <name>`.
- HOẶC `TeamCreate` báo: `Already leading team "<old>"` dù tưởng team đã chết.
- HOẶC agent trước đó báo cáo bình thường, rồi **im hẳn** sau một sự kiện hệ thống (docker restart, OOM, host load cao, máy sleep).

→ Đừng vội kết luận "agent đang bận". Nghi **orphan** ngay.

---

## 2. Chẩn đoán CHÍNH XÁC (3 lệnh — đây là FACT, không đoán)

```bash
# (a) pane nào còn sống trong tmux?
tmux list-panes -a -F "#{pane_id}"

# (b) lấy tmuxPaneId của từng member
python3 -c "import json,subprocess;
d=json.load(open('$HOME/.claude/teams/<TEAM>/config.json'));
alive=subprocess.run(['tmux','list-panes','-a','-F','#{pane_id}'],capture_output=True,text=True).stdout.split();
[print(m['name'],'pane',m.get('tmuxPaneId',''),'→','ALIVE' if m.get('tmuxPaneId','') in alive else 'DEAD') for m in d['members']]"
```

- Member có `tmuxPaneId` KHÔNG nằm trong `list-panes` = **DEAD orphan** (chắc chắn).
- Inbox `~/.claude/teams/<TEAM>/inboxes/<name>.json` > 2 bytes = có message chưa xử lý (pane chết không đọc).

**Cơ chế (đã verify):** agent chạy trong tmux pane. Pane chết → message vẫn ghi vào inbox.json (gửi "success") nhưng KHÔNG có process đọc/reply → "nhận được nhưng câm". Registry/harness check liveness lazy nên vẫn hiển thị "active" (stale).

**CHƯA chắc 100% (đoán, khả năng cao):** *tại sao* đúng pane đó chết (OOM-killer? tmux nhận SIGTERM khi docker/systemd restart? agent session tự exit?) + *cơ chế chính xác* harness cập nhật "active". Muốn chắc → đọc code harness phần tmux-liveness + `journalctl`/tmux log lúc pane chết. Với vận hành hằng ngày, chẩn đoán §2 là đủ.

---

## 3. Xử lý

### Case A — vài agent chết, vài còn sống (orphan lẻ)
1. `SendMessage` shutdown_request tới agent dead. Nếu nó terminate → xong.
2. Nếu kẹt (pane chết không xử lý được shutdown): **sửa `config.json` bỏ member dead**, GIỮ member sống.
   ```bash
   cp ~/.claude/teams/<TEAM>/config.json ~/.claude/teams/<TEAM>/config.json.bak   # backup
   # rồi xóa member dead khỏi mảng members (python/jq), giữ team-lead + agent sống
   ```
3. Kill pane dead nếu còn xác: `tmux kill-pane -t %<id>` (thường đã tự chết).

### Case B — cả team chết / TeamDelete kẹt (nên dùng — sạch nhất)
1. (tuỳ chọn) kill pane agent còn sống để khỏi orphan chạy nền: `tmux kill-pane -t %<id>`.
2. **Xóa team dir trên disk** (TeamDelete tool sẽ kẹt vì "active member"):
   ```bash
   rm -rf ~/.claude/teams/<TEAM>
   rm -rf ~/.claude/tasks/<TEAM>
   ```
3. Gọi `TeamDelete` (giờ file đã xóa → nó clear context "leading <TEAM>" của session, trả success).
4. `TeamCreate` team **TÊN MỚI** (đừng tái dùng tên cũ — orphan/shutdown-request cũ có thể match nhầm agent mới).
5. **Spawn 1 agent haiku test comms TRƯỚC** (canary): nhiệm vụ duy nhất = gửi 1 reply về team-lead. Nếu reply về → comms OK → dựng full team. Nếu im → comms còn lỗi, điều tra tiếp (đừng dựng full).
6. Shutdown canary, rồi spawn team thật.

---

## 4. Phòng ngừa

- **mem/cpu limit cho container** (life-os: BE 1g/FE 2g + cpus 2.0 trong docker-compose.yml) → host-overload khó giết pane.
- **KHÔNG `docker stop docker` / lệnh hệ thống nặng khi team đang chạy** — nó giết pane agent giữa chừng = orphan. Nếu phải làm, shutdown team gracefully trước.
- **Tên team mới mỗi lần rebuild** (life-os-r2 → lifeos-w1 → ...) — orphan cũ không match.
- **Pre-flight haiku comms-test** trước khi dựng full team — rẻ, bắt orphan/comms sớm (1 agent thay vì phát hiện sau khi spawn 4).
- Theo dõi `uptime`/load: load >~20 trên máy nhiều-app là cảnh báo; pane dễ chết khi load 100+.

---

## 5. Quick reference (dán nhanh khi gặp)
```bash
# orphan check
tmux list-panes -a -F "#{pane_id}"
ls ~/.claude/teams/        # team nào còn
# nuke 1 team
rm -rf ~/.claude/teams/<TEAM> ~/.claude/tasks/<TEAM>
# rồi TeamDelete (clear context) → TeamCreate <tên-mới> → spawn haiku canary → test → dựng full
```
</content>
