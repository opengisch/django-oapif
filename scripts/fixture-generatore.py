#!/usr/bin/env python
import json

magnitude = 100
x_start = 45  # 2508500
y_start = 7  # 1152000
step = 0.01
signs_per_pole = 3
pole_file = "signalo/signalo_app/fixtures/pole.json"
sign_file = "signalo/signalo_app/fixtures/sign.json"

######

if __name__ == "__main__":
    poles = []
    signs = []

    for dx in range(0, magnitude):
        for dy in range(0, magnitude):
            # pole
            x = x_start + dx * step
            y = y_start + dy * step
            pole_pk = f"00000000-0000-0000-0002-{dx:06d}{dy:06d}"
            geom = f"Point({x} {y})"
            name = f"{dx}-{dy}"

            poles.append(
                {
                    "model": "signalo_app.pole",
                    "pk": pole_pk,
                    "fields": {"geom": geom, "name": name},
                }
            )

            # signs
            for s in range(0, signs_per_pole):
                order = s + 1
                signs.append(
                    {
                        "model": "signalo_app.sign",
                        "pk": f"{dx:04d}{dy:04d}-0000-0000-0003-{order:012d}",
                        "fields": {"order": order, "pole": pole_pk},
                    }
                )

    with open(pole_file, "w+") as pole_fh:
        json.dump(poles, pole_fh, indent=2)
    with open(sign_file, "w+") as sign_fh:
        json.dump(signs, sign_fh, indent=2)
