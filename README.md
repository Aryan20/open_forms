# OpenForms


<img width="100" height="100" alt="in aryank openforms" src="https://github.com/user-attachments/assets/f99829cc-cb74-4883-ab3c-e8ad13e741e3" />



**OpenForms** is a simple, local-first form collection app for GNOME.  
It is designed for situations where setting up online forms is impractical or unreliable — such as conferences, meetups, workshops, or community events.

OpenForms works fully offline, stores responses locally, and avoids unnecessary complexity.

---

## Why OpenForms?

The idea for OpenForms began during a discussion at a conference.

At many conferences and events, collecting information through online forms often becomes frustrating due to:
- Unreliable or congested networks
- Failing Wi-Fi chipsets
- Captive portals, passwords, and timeouts
- Services that simply don’t work when you need them

In such scenarios, a small, no-fuss, offline-friendly form collection tool makes far more sense.

After searching for existing solutions and not finding anything that fit this use case well, OpenForms was built to fill that gap.

## Screenshots
<img height="400" alt="Screenshot From 2025-12-14 20-22-20" src="https://github.com/user-attachments/assets/ef136732-46cf-4eb4-ba0f-6dc06062d6df" /> <img height="400" alt="Screenshot From 2025-12-14 20-22-24" src="https://github.com/user-attachments/assets/0aee53f6-e31f-488f-9ccf-195c6da38319" /> <img height="400" alt="Screenshot From 2025-12-14 20-22-37" src="https://github.com/user-attachments/assets/b2ea9a92-6275-4a7a-bbf5-ca2449f6cdc2" /> <img height="400" alt="Screenshot From 2025-12-14 20-25-13" src="https://github.com/user-attachments/assets/96f8b18e-1dfa-4238-bab5-53f11f61dcb6" />




---

## Features

### Current
- Create structured forms using a simple configuration format
- Collect responses locally and store them in **CSV** format
- Attach images using the system file picker
- Clean integration with **GNOME**
- Sandboxed distribution via **Flatpak**

### Planned
- Create form configurations directly from the GUI (no manual JSON editing)
- Support for making fields required
- Strong form validation
- Form history to quickly open them again

---

## Privacy & Permissions

OpenForms is built with a **privacy-first, local-first** philosophy.

- ❌ No network access
- ❌ No tracking or analytics
- ❌ No accounts or cloud services
- ✅ All data stays on your device

The app only requests **pictures access**, which is used exclusively for attaching images to form entries via the system file picker.

---

## Use Cases

- Conference or meetup registrations
- Workshop attendance tracking
- Offline surveys
- Temporary data collection at events
- Any scenario where internet access cannot be relied upon

---

## Installation

### Flatpak (recommended)

Please use the latest release or build using GNOME Builder.

## Sample Config

```json
{
  "form_name": "OpenForms – User Feedback",
  "fields": [
    {
      "id": "title",
      "type": "label",
      "label": "OpenForms Feedback",
      "style": ["title-1"]
    },

    {
      "id": "subtitle",
      "type": "label",
      "label": "Help us improve by sharing your experience",
      "style": ["subtitle"]
    },

    {
      "id": "hero_image",
      "type": "picture",
      "label": "OpenForms logo",
      "uri": "file:///home/aryan/Pictures/OpenForms.png",
      "width": 480,
      "height": 200
    },

    {
      "id": "name",
      "type": "entry",
      "label": "Your name",
      "required": true
    },

    {
      "id": "email",
      "type": "entry",
      "label": "Email address"
    },

    {
      "id": "usage_type",
      "type": "radio",
      "label": "How are you using OpenForms?",
      "options": [
        "Personal use",
        "Education",
        "Work / Research",
        "Just exploring"
      ]
    },
    {
      "id": "i_agree_to_submit",
      "type": "check",
      "label": "I agree to submit"
    },
    {
      "id": "comments",
      "type": "text",
      "label": "Additional comments or suggestions"
    },
    {
      "id": "first_start",
      "type": "calendar",
      "label": "When did you first started using OpenForms?"
    },
    {
      "id": "rating",
      "type": "spin",
      "label": "What rating would you give OpenForms?",
      "min": 0,
      "max": 5,
      "step": 1
    }
  ]
}
