/* eslint-disable no-unused-vars */
const PREVIEW_GAMES = [
    { id: 1, title: "Arma 3" },
    { id: 2, title: "DayZ" },
    { id: 3, title: "Reforger" },
];

const PREVIEW_SQUADS = [
    { id: 1, name: "Альфа", tags: [], games: [PREVIEW_GAMES[0], PREVIEW_GAMES[1]] },
    { id: 2, name: "Бета", tags: [], games: [PREVIEW_GAMES[0], PREVIEW_GAMES[2]] },
];

function previewSchedule(gameId, title, day = 5, time = "20:00:00") {
    return {
        schedule_preset: {
            id: 100 + gameId,
            title,
            game_day_of_week: day,
            game_time: time,
            game: PREVIEW_GAMES.find((g) => g.id === gameId),
        },
        attend_status: null,
        comment: "",
    };
}

function previewSummaryItem(gameId, title) {
    return {
        schedule_preset: {
            id: 100 + gameId,
            title,
            game_day_of_week: 5,
            game_time: "20:00:00",
            game: PREVIEW_GAMES.find((g) => g.id === gameId),
        },
        players: [
            { player_name: "Игрок1", attend_status: "will_attend", comment: "" },
            { player_name: "Игрок2", attend_status: "doubts", comment: "может опоздать" },
            { player_name: "Игрок3", attend_status: "will_not_attend", comment: "" },
        ],
    };
}

const PREVIEW_ADMIN_MOCK = {
    members: [
        { telegram_id: 101, display_name: "Андрей", name: "Игрок1", is_telegram_admin: true },
        { telegram_id: 102, display_name: "Пётр", name: "Игрок2", is_telegram_admin: false },
        { telegram_id: 103, display_name: "Сергей", name: "Игрок3", is_telegram_admin: false },
    ],
    friends: [{ id: 201, name: "ДругОтряда" }],
    requests: [{ id: 301, player_name: "Новенький", request_type: "join" }],
    blocked: [],
    pendingCount: 2,
    schedulePresets: [
        {
            id: 501,
            title: "Основная игра",
            recurrence_type: "weekly",
            game_day_of_week: 5,
            game_time: "20:00:00",
            game: PREVIEW_GAMES[0],
        },
        {
            id: 502,
            title: "Сбор перед выходными",
            recurrence_type: "monthly",
            day_of_month: 15,
            game_day_of_week: 4,
            game_time: "19:30:00",
            game: PREVIEW_GAMES[1],
        },
    ],
};

const PREVIEW_SCENARIOS = {
    1: {
        label: "Одиночка · личка",
        launch: { source: "dm", squad_id: null },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 1, squad_id: null, squad_name: null, telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: null,
            context_squad_id: null,
            player: { id: 1, squad_id: null, squad_name: null, telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: false,
            is_admin_of_squad_id: null,
            squad_relation: null,
        },
        attendances: [],
        summary: [],
        admin: null,
    },
    2: {
        label: "Одиночка · чат отряда",
        launch: { source: "squad_chat", squad_id: 1 },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 1, squad_id: null, squad_name: null, telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: null,
            context_squad_id: 1,
            player: { id: 1, squad_id: null, squad_name: null, telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: false,
            is_admin_of_squad_id: null,
            squad_relation: "outsider",
        },
        attendances: [
            previewSchedule(1, "Основная игра", 5),
            previewSchedule(2, "Второстепенная", 6),
        ],
        summary: [],
        admin: null,
    },
    3: {
        label: "Отрядник · личка",
        launch: { source: "dm", squad_id: null },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: 2,
            context_squad_id: 2,
            player: { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: false,
            is_admin_of_squad_id: null,
            squad_relation: "member",
        },
        attendances: [
            previewSchedule(1, "Тренировка", 4),
            previewSchedule(3, "Операция", 6),
        ],
        summary: [previewSummaryItem(1, "Тренировка")],
        admin: null,
    },
    4: {
        label: "Отрядник · свой чат",
        launch: { source: "squad_chat", squad_id: 2 },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: 2,
            context_squad_id: 2,
            player: { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: false,
            is_admin_of_squad_id: null,
            squad_relation: "member",
        },
        attendances: [
            previewSchedule(1, "Тренировка", 4),
            previewSchedule(3, "Операция", 6),
        ],
        summary: [previewSummaryItem(1, "Тренировка")],
        admin: null,
    },
    5: {
        label: "Отрядник · чужой чат",
        launch: { source: "squad_chat", squad_id: 1 },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: 2,
            context_squad_id: 1,
            player: { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: false,
            is_admin_of_squad_id: null,
            squad_relation: "outsider",
        },
        attendances: [previewSchedule(1, "Основная игра", 5)],
        summary: [],
        admin: null,
        ownSquad: { id: 2, name: "Бета" },
    },
    6: {
        label: "Админ · чужой чат",
        launch: { source: "squad_chat", squad_id: 1 },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: 2,
            context_squad_id: 1,
            player: { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: true,
            is_admin_of_squad_id: 2,
            squad_relation: "outsider",
        },
        attendances: [previewSchedule(1, "Основная игра", 5)],
        summary: [],
        admin: PREVIEW_ADMIN_MOCK,
        ownSquad: { id: 2, name: "Бета" },
    },
    7: {
        label: "Админ · свой чат",
        launch: { source: "squad_chat", squad_id: 2 },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: 2,
            context_squad_id: 2,
            player: { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: true,
            is_admin_of_squad_id: 2,
            squad_relation: "member",
        },
        attendances: [
            previewSchedule(1, "Тренировка", 4),
            previewSchedule(3, "Операция", 6),
        ],
        summary: [previewSummaryItem(1, "Тренировка")],
        admin: PREVIEW_ADMIN_MOCK,
    },
    8: {
        label: "Админ · личка",
        launch: { source: "dm", squad_id: null },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
                { id: 3, squad_id: 1, squad_name: "Альфа", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: 2,
            context_squad_id: 2,
            player: { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: true,
            is_admin_of_squad_id: 2,
            squad_relation: "member",
        },
        attendances: [
            previewSchedule(1, "Тренировка", 4),
            previewSchedule(3, "Операция", 6),
        ],
        summary: [previewSummaryItem(1, "Тренировка")],
        admin: PREVIEW_ADMIN_MOCK,
    },
    9: {
        label: "Одиночка · группа без отряда · админ",
        launch: { source: "squad_chat", squad_id: null },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 1, squad_id: null, squad_name: null, telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: null,
            context_squad_id: null,
            player: { id: 1, squad_id: null, squad_name: null, telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: false,
            is_admin_of_squad_id: null,
            can_create_squad: true,
            squad_relation: null,
        },
        attendances: [],
        summary: [],
        admin: null,
    },
    10: {
        label: "Свой отряд · заявка в чужой",
        launch: { source: "squad_chat", squad_id: 1 },
        me: {
            telegram_id: 9001,
            telegram_tag: "preview",
            display_name: "Preview User",
            memberships: [
                { id: 1, squad_id: null, squad_name: null, telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
                { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            ],
            primary_squad_id: 2,
            context_squad_id: 1,
            player: { id: 2, squad_id: 2, squad_name: "Бета", telegram_id: 9001, telegram_tag: "preview", name: "НикИгрока", games: [] },
            is_squad_admin: true,
            is_admin_of_squad_id: 2,
            squad_relation: "pending",
        },
        attendances: [previewSchedule(1, "Основная игра", 5)],
        summary: [],
        admin: PREVIEW_ADMIN_MOCK,
    },
};

window.PREVIEW_SCENARIOS = PREVIEW_SCENARIOS;
window.PREVIEW_SQUADS = PREVIEW_SQUADS;
window.PREVIEW_GAMES = PREVIEW_GAMES;
