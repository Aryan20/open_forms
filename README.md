# OpenForms

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
    },

    {
      "id": "email",
      "type": "entry",
      "label": "Email address",
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
      ],
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
    }
  ]
}
