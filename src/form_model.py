# form_model.py
#
# Copyright 2025 Aryan Kaushik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import uuid
from dataclasses import dataclass, field


@dataclass
class FormField:
    """
    Represents one field in the form config JSON.
    Only keys relevant to the field type are emitted on serialisation,
    mirroring exactly what form_page.py's _create_field() expects.
    """

    type: str
    label: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    required: bool = False
    # radio / dropdown
    options: list = field(default_factory=list)
    # spin
    min: float = 0
    max: float = 10
    step: float = 1
    # label / title
    style: list = field(default_factory=list)
    # picture
    uri: str = ""
    width: int = 480
    height: int = 200
    # entry / text
    placeholder: str = ""
    # shown below the label for most interactive fields
    help_text: str = ""

    def to_dict(self) -> dict:
        """Emit only the keys that form_page.py actually reads."""
        base = {"id": self.id, "type": self.type, "label": self.label}

        if self.type in ("entry", "text", "check", "radio", "calendar", "dropdown"):
            if self.required:
                base["required"] = True

        if self.type in ("radio", "dropdown"):
            base["options"] = list(self.options)

        if self.type == "spin":
            base["min"] = self.min
            base["max"] = self.max
            base["step"] = self.step

        if self.type == "label":
            base["style"] = list(self.style)

        if self.type == "picture":
            base["uri"] = self.uri
            base["width"] = self.width
            base["height"] = self.height

        if self.type in ("entry", "text") and self.placeholder:
            base["placeholder"] = self.placeholder

        if self.type in ("entry", "text", "dropdown", "radio", "check", "spin", "calendar") and self.help_text:
            base["help_text"] = self.help_text

        return base

    @classmethod
    def from_dict(cls, d: dict) -> "FormField":
        return cls(
            type=d.get("type", "entry"),
            label=d.get("label", ""),
            id=d.get("id", str(uuid.uuid4())[:8]),
            required=d.get("required", False),
            options=list(d.get("options", [])),
            min=d.get("min", 0),
            max=d.get("max", 10),
            step=d.get("step", 1),
            style=list(d.get("style", [])),
            uri=d.get("uri", ""),
            width=d.get("width", 480),
            height=d.get("height", 200),
            placeholder=d.get("placeholder", ""),
            help_text=d.get("help_text", ""),
        )


@dataclass
class FormModel:
    form_name: str = "New Form"
    fields: list = field(default_factory=list)  # list[FormField]
    kiosk: dict = field(default_factory=dict)

    def to_json(self) -> str:
        doc = {
            "form_name": self.form_name,
            "fields": [f.to_dict() for f in self.fields],
        }
        if self.kiosk:
            doc["kiosk"] = self.kiosk
        return json.dumps(doc, indent=2, ensure_ascii=False)

    @classmethod
    def from_json_string(cls, s: str) -> "FormModel":
        d = json.loads(s)
        return cls(
            form_name=d.get("form_name", "New Form"),
            fields=[FormField.from_dict(f) for f in d.get("fields", [])],
            kiosk=d.get("kiosk", {}),
        )

    @classmethod
    def from_file(cls, path: str) -> "FormModel":
        with open(path, encoding="utf-8") as f:
            return cls.from_json_string(f.read())
