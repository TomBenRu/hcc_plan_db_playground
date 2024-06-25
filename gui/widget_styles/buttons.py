import dataclasses

# maps time_of_day_enum.time_index to style

avail_day__event: dict[int, str] = {
    1: "QPushButton {background-color: #cae4f4; border-radius: 5px;}"
       "QPushButton::checked { background-color: #002aaa; border: 2px solid #002aaa; border-top: 2px solid #001970; border-left: 2px solid #001970; border-bottom: 2px solid #0039d9; border-right: 2px solid #0039d9; padding: 2px;}"
       "QPushButton::disabled { background-color: #6a7585;}",
    2: "QPushButton {background-color: #fff4d6; border-radius: 5px;}"
       "QPushButton::checked { background-color: #ff4600; border: 2px solid #ff4600; border-top: 2px solid #cc3700; border-left: 2px solid #cc3700; border-bottom: 2px solid #ff6f33; border-right: 2px solid #ff6f33; padding: 2px;}"
       "QPushButton::disabled { background-color: #7f7f7f;}",
    3: "QPushButton {background-color: #daa4c9; border-radius: 5px;}"
       "QPushButton::checked { background-color: #84033c; border: 2px solid #84033c; border-top: 2px solid #670029; border-left: 2px solid #670029; border-bottom: 2px solid #a50048; border-right: 2px solid #a50048; padding: 2px;}"
       "QPushButton::disabled { background-color: #674b56;}",
    4: "QPushButton {background-color: #a9a9a9; border-radius: 5px;}"
       "QPushButton::checked { background-color: #686868; border: 2px solid #686868; border-top: 2px solid #505050; border-left: 2px solid #505050; border-bottom: 2px solid #808080; border-right: 2px solid #808080; padding: 2px;}"
       "QPushButton::disabled { background-color: #a9a9a9;}"
}
