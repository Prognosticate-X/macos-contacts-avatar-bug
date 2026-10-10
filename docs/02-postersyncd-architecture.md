# Architecture Analysis: postersyncd, CardDAV, and AvatarViewSnapshotter

## 1. Overview of macOS 27 Contact Likeness Subsystems

macOS 27 overhauled the Contact Poster and Avatar infrastructure to mirror iOS's Contact Poster system. Under the hood, this involves three distinct layers:

1. **CardDAV Storage Layer (`AddressBookSourceSync`)**:
   - Manages traditional contact metadata (Name, Phone, Email, Note, and raw bitmap `imageData` / `thumbnailImageData`).
   - Syncs with `p*-contacts.icloud.com`.
2. **Contact Poster & Metadata Daemon (`postersyncd`)**:
   - Manages full-screen posters, Memoji vector archives, typography, and wallpaper configurations.
   - Communicates over XPC (`com.apple.contacts.poster.api`).
3. **UI Rendering & Snapshotting Layer (`ContactsUI.framework`)**:
   - `AvatarViewSnapshotter`: Generates cached snapshot representations for contact bubbles in Contacts and Messages.
   - `avatar-decorator`: Checks whether a contact has an active poster (`Contains wallpaper key`) or Memoji metadata (`avatarRecipeData`).

---

## 2. The Collision: Modern Vector Architecture vs. Legacy CardDAV Bitmaps

When an avatar is edited in Contacts.app:
- Contacts rasterizes the avatar into a PNG/JPEG bitmap (`imageType PHOTO`, ~19KB to ~110KB).
- It writes this image to `AddressBook-v22.abcddb` via CoreData and pushes it to CardDAV.
- However, when no custom Contact Poster has been assigned, the modern poster metadata store contains no vector definition (`avatarRecipeData = nil`).

When `postersyncd` and the Contacts framework process external change notifications, they query the contact with modern descriptors:
```text
Contains wallpaper key: 0
Skipping: required keys missing
AvatarRecipeData not currently fetched on ContactID
No avatarRecipeData on ContactID
```

Combined with the `Could not fetch group for change type 1, making it a delete change type` error, `AvatarViewSnapshotter` encounters a contact marked as **"Likeness Deleted"** that **lacks an avatar recipe**. Instead of falling back to the legacy `thumbnailImageData` stored in the CardDAV database, it immediately falls back to rendering a generated monogram (initial letter) and commits this blank snapshot to the UI cache.

---

## 3. Why Local Resets Fail

During exhaustive testing, the following remediation attempts were verified ineffective:
1. **Disabling and re-enabling iCloud Contacts**: Fails because the server-side image triggers the exact same APNS push and change history bug upon re-download.
2. **Deleting `~/Library/Application Support/AddressBook`**: Fails because upon initial synchronization from iCloud, the delta processor hits the same code path.
3. **Clearing SwiftData `accounts.accountdb`**: Fails because account authentication is unaffected.
4. **Modifying from iPhone or iCloud.com**: Fails on Mac because as soon as the Mac receives the remote update, it runs the same flawed change history parser.
5. **Updating to macOS 27.0.1**: Fails because the underlying fallback logic in `Contacts.framework` remains unpatched in macOS 27.0.1.

**Conclusion**: The issue is entirely caused by an upstream logic error within `Contacts.framework` and `ContactsUI.framework` in macOS 27.0, and has been confirmed to **still persist in macOS 27.0.1**. It can only be permanently resolved by an official bug fix from Apple (e.g., macOS 27.0.2 or 27.1).
