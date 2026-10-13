# macOS 27 Contacts Avatar Reversion Regression Analysis & Diagnostic Tool

[![Platform](https://img.shields.io/badge/Platform-macOS%2027.0%20%7C%2027.0.1-blue.svg)](#)
[![Status](https://img.shields.io/badge/Status-Regression%20Confirmed-red.svg)](#)
[![Workaround](https://img.shields.io/badge/Workaround-Sign%20Out%20%26%20In%20Apple%20Account-success.svg)](#3--verified-workaround-how-to-fix-it-now)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Apple Radar](https://img.shields.io/badge/Apple%20Radar-FB25131637-orange.svg)](#5-how-to-submit-a-duplicate-report-to-apple)

[English](#english) | [中文说明](#中文说明)

---

<a name="english"></a>
## English

### 1. Issue Overview

In **macOS 27.0 (Build 26A428)** and **macOS 27.0.1** (tested and confirmed still persisting in 27.0.1), whenever a user updates a contact's avatar (using custom photos, Memoji, or Emoji) in Contacts or Messages, the avatar displays normally for a few seconds, but **automatically reverts to the default monogram initial (e.g. "T") after approximately 15 to 20 seconds**.

#### Key Observations:
- **iPhone / iOS Works Correctly**: When changing the avatar on iPhone, it persists permanently on iOS. However, when synced down to Mac, the Mac still reverts to the monogram initial.
- **iCloud Web Works Correctly**: Uploading via icloud.com is permanent on the cloud, but triggers the same reversion on macOS.
- **Affects All Media Types**: Custom photos, Memoji, and Emoji all revert.
- **Local Cache Resets Do Not Help**: Deleting `~/Library/Application Support/AddressBook`, resetting `accounts.accountdb`, or toggling iCloud contacts does not fix the issue.

---

### 2. Root Cause Analysis

Through millisecond-level unified log tracing (`log stream`), we identified the definitive root cause within `Contacts.framework` and `ContactsUI.framework`:

```text
[User saves Avatar in Contacts.app]
       │
       ▼ (T+0s)
1. Commit edit: Image rasterized to 19KB PHOTO and saved locally.
       │
       ▼ (T+12s)
2. CardDAV Sync: AddressBookSourceSync uploads photo to iCloud (HTTP 207 Success).
       │
       ▼ (T+15s)
3. APNS Push Return: Apple Push Notification arrives acknowledging the change.
       │
       ▼ (T+16s) ───► 【FATAL REGRESSION IN macOS 27】
4. ChangeHistory Engine: Core daemons query change history. Because the contact
   lacks a custom group container, the fallback handler incorrectly executes:
   "Could not fetch group for change type 1 ..., making it a delete change type."
   (The UPDATE event is erroneously mutated into a DELETE event!)
       │
       ▼ (T+16.1s)
5. AvatarViewSnapshotter: ContactsUI receives the false "Delete" notification,
   finds no vector recipe (No avatarRecipeData), snaps a fallback monogram initial,
   and overrides the UI cache.
```

Detailed technical write-ups are available in the [`docs/`](./docs/) directory:
- [01. In-Depth Root Cause & Evidence Log](./docs/01-technical-root-cause.md)
- [02. postersyncd & AvatarViewSnapshotter Architecture](./docs/02-postersyncd-architecture.md)

---

### 3. ✅ Verified Workaround (How to Fix It Now)

If your Mac is experiencing this issue on macOS 27 or 27.0.1, we have tested and verified that **completely signing out of your Apple Account and signing back in** permanently resolves the problem:

#### Step-by-Step Instructions:
1. Open **System Settings** on your Mac.
2. Click on your **Apple Account** (your profile at the top of the sidebar).
3. Scroll to the bottom and click **Sign Out**. *(When prompted whether to keep a copy of your data on this Mac, you can choose to keep copies).*
4. Once signed out, restart your Mac.
5. Re-open **System Settings**, sign back into your Apple Account, and ensure **Contacts** synchronization is enabled.
6. Open Contacts.app and set your avatars—they will now stick permanently and never revert!

#### Technical Rationale (Why this works):
* **Why toggling Contacts or clearing `AddressBook` fails:** Merely toggling the sync switch or removing local database files leaves the underlying Account Source GUID bindings and CloudKit subscriptions in `accounts.accountdb` intact, preserving the desynced container mapping.
* **Why signing out works:** Completely signing out destroys the entire CardDAV account session and tears down the desynced local container hierarchy.
* **Why signing back in fixes it:** Re-authenticating provisions a clean CardDAV group and container structure fresh from iCloud. The Contacts framework can now successfully fetch the parent group (`fetchGroupForChange`), which prevents the faulty `making it a delete change type` fallback from being triggered.

---

### 4. Diagnostic Tool

We provide a built-in automated CLI tool to verify if your Mac is suffering from this bug.

#### Step 1: Capture live logs while reproducing the issue
```bash
./tools/capture_contacts_log.sh
```
1. Keep the terminal running.
2. Open **Contacts.app**, edit any contact's avatar, and click **Done**.
3. Wait ~20 seconds until you see the avatar revert.
4. Press `Ctrl+C` in the terminal. The script will automatically generate a sanitized log.

#### Step 2: Run automated log diagnosis
```bash
python3 ./tools/analyze_log.py ./samples/sanitized_reproduction.log
```
The analyzer will parse the timestamps and output:
```text
====================================================================
   macOS Contacts Bug Automated Log Analyzer                       
====================================================================
[*] Detection Summary:
  • Contact Save/Commit Events detected: 3
  • CardDAV Server Push (Status 207) detected: 6
  • APNS Push Notifications detected: 1
  • 'Change Type 1 -> Delete Change Type' triggers: 24
  • AvatarViewSnapshotter Override Events: 270

[✔ BUG CONFIRMED] macOS 27 ChangeHistoryFetch Regression Detected!
Elapsed Duration from Save to Reversion: 19.34 seconds
```

---

### 5. How to Submit a Duplicate Report to Apple

**Primary Apple Feedback / Radar ID: `FB25131637`**

To expedite an official fix from Apple, please submit a duplicate bug report via **Feedback Assistant** referencing the primary feedback ID **`FB25131637`**:

1. Open **Feedback Assistant** on your Mac (`open applefeedback://` or press `Cmd+Space` and type *Feedback Assistant*).
2. Click **New Feedback** -> **macOS** -> **Contacts**.
3. Copy the template below:

```markdown
### Title
[macOS 27.0 / 27.0.1 Regression] Contact avatar reverts to monogram initial after 15-20s due to ChangeHistoryFetch classifying update as delete

### Reference Primary Radar
Duplicate of: FB25131637

### Problem Description
In macOS 27.0 (Build 26A428) and macOS 27.0.1 (confirmed still present after upgrading to 27.0.1), editing any contact avatar (Memoji, photo, or emoji) saves temporarily, but automatically reverts to the default monogram letter initial after ~16 seconds.

The change syncs to iCloud and displays permanently on iOS, but every Mac receiving the sync triggers the regression.

### Underlying Log Evidence
All listening daemons (Messages, Contacts, contactsd, postersyncd, AddressBookSourceSync) log:
"Could not fetch group for change type 1 with identifier <private>, making it a delete change type."
Followed by:
"AvatarViewSnapshotter: No avatarRecipeData on ContactID -> generate monogram fallback"

Reference GitHub repository and logs:
https://github.com/Prognosticate-X/macos-contacts-avatar-bug
```
4. Attach the sanitized log file [`samples/sanitized_reproduction.log`](./samples/sanitized_reproduction.log).

---

<a name="中文说明"></a>
## 中文说明

### 1. 问题概述

在 **macOS 27.0 正式版（Build 26A428）及最新更新 macOS 27.0.1** 中（实测升级至 27.0.1 后缺陷依然存在），用户在通讯录（Contacts.app）或信息（Messages.app）中修改联系人头像（无论是自定义照片、系统 Emoji 还是拟我表情 Memoji），保存后在界面上正常显示数秒，但在 **15 ~ 20 秒左右会自动回退为默认的单字母占位符**（例如 Test 回退为大写字母“T”）。

#### 核心特征：
* **iPhone 端完全正常**：在 iPhone 上修改头像能永久保存，绝不回退；但只要同步到 Mac，Mac 依然会在数秒后回退为字母。
* **全媒介格式均受影响**：照片、Emoji、Memoji 无一幸免。
* **本地重置与小版本升级完全无效**：清空 AddressBook 缓存目录、重置 SwiftData `accounts.accountdb`、开关 iCloud 通讯录，或升级到 macOS 27.0.1 均无法解决。

---

### 2. 根本技术成因

通过对统一日志系统（Unified Logging）毫秒级追踪，定位到这是 `Contacts.framework` 联系人变更历史解析引擎中的代码级缺陷：

1. **第 0 秒**：通讯录正常将图片以 19KB 位图存盘。
2. **第 12 秒**：`AddressBookSourceSync` 将头像成功推送至 iCloud CardDAV（状态码 207 成功），这是 iPhone 端能长期保存的原因。
3. **第 15 秒**：苹果 APNS 推送回执到达 Mac，Mac 完成增量存储并广播变更。
4. **第 16 秒【致命 Bug 触发点】**：
   系统 5 大核心进程（Contacts、Messages、contactsd、postersyncd、AddressBookSourceSync）拉取变更历史。由于未关联独立群组容器，底层的降级逻辑错误地抛出：
   `Could not fetch group for change type 1 ..., making it a delete change type.`
   **代码强行将“更新事件（type 1）”错误标记成了“删除事件（delete）”！**
5. **第 16.1 秒**：
   前端快照器 `AvatarViewSnapshotter` 收到被篡改的删除事件，判定无矢量配方（`No avatarRecipeData`），立刻拍下默认单字母快照并覆写界面缓存。

详细深度分析请参阅文档：
* [01. 根本原因深度分析与日志证据链](./docs/01-technical-root-cause.md)
* [02. postersyncd 与快照器架构机理](./docs/02-postersyncd-architecture.md)

---

### 3. ✅ 已验证有效解决方案（如何立即解决）

如果你在 macOS 27 或 27.0.1 中遇到了此问题，我们已实测并验证：**在系统设置中完全退出 Apple 账户并重新登录** 可以彻底解决该问题，头像不再回退！

#### 具体操作步骤：
1. 打开 Mac 上的 **系统设置**。
2. 点击左上角的 **Apple 账户**（你的头像与名字）。
3. 滑动到底部，点击 **退出登录**（系统提示是否在 Mac 上保留通讯录等数据副本时，可选择保留副本）。
4. 退出完成后，建议重启一次 Mac。
5. 重新打开 **系统设置**，重新登录你的 Apple 账户，并确保勾选开启 **通讯录** 同步。
6. 打开通讯录重新修改头像——头像将稳固保存，不会再自动回退！

#### 深入技术原理解密（为什么有效）：
* **为什么之前单独“开关通讯录同步”或“删除 `AddressBook` 缓存”无效？**  
  因为 macOS 系统级的账户数据库（`accounts.accountdb`）仍保留着旧的 Account Source GUID 与失效的群组映射通道，重新拉取依然找不到对应群组。
* **为什么“完全登出 Apple ID 并重新登录”有效？**  
  完全登出会彻底销毁系统层所有陈旧的 CardDAV 映射凭证与 CloudKit 订阅管道；重新登录时，系统会从云端完整拉取并重建一套全新的容器群组架构。此时本地联系人框架能正常获取所属群组（`fetchGroupForChange`），系统不会再触发 `making it a delete change type` 的伪造删除逻辑，头像因此得以永久稳固保存！

---

### 4. 自助诊断工具使用

本项目自带轻量化自动化诊断工具，可在终端一键验证：

```bash
# 1. 启动实时抓取脚本（根据提示在通讯录修改头像，等待回退后按 Ctrl+C）
./tools/capture_contacts_log.sh

# 2. 运行自动分析器对抓取的日志进行诊断
python3 ./tools/analyze_log.py ./samples/sanitized_reproduction.log
```

---

### 5. 推动苹果官方修复指南

**主工单编号（Primary Apple Feedback ID）：`FB25131637`**

该问题属于 macOS 27 的系统底层代码缺陷，且**实测更新 macOS 27.0.1 后仍未解决**。

建议所有遇到此问题的用户通过 Mac 自带的 **反馈助理（Feedback Assistant）** 提交 Duplicate 工单，在反馈描述中注明关联主工单 **`FB25131637`**，并附件上传本项目提供的脱敏日志 [`samples/sanitized_reproduction.log`](./samples/sanitized_reproduction.log)，形成联名效应，共同敦促苹果工程团队尽快在后续版本中彻底修复。

---

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.
