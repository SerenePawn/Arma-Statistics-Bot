from logic.attendances.enums import AttendStatus

ATTENDANCE_EMOJI = {
    AttendStatus.WILL_ATTEND: "🟢",
    AttendStatus.DOUBTS: "🟡",
    AttendStatus.WILL_NOT_ATTEND: "🔴",
    True: "🟢",
    False: "🔴",
    None: "🔵",
}