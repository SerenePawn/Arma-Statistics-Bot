(function initPreview() {
    const params = new URLSearchParams(window.location.search);
    if (!params.has("preview")) {
        return;
    }

    window.__previewDeferLoad = true;

    let currentScenarioId = Number(params.get("scenario")) || 1;
    let previewState = null;

    function clone(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function applyScenario(id) {
        const scenario = window.PREVIEW_SCENARIOS[id];
        if (!scenario) {
            return;
        }

        currentScenarioId = id;
        previewState = {
            me: clone(scenario.me),
            launch: clone(scenario.launch),
            squads: clone(window.PREVIEW_SQUADS),
            games: clone(window.PREVIEW_GAMES),
            attendances: clone(scenario.attendances),
            summary: clone(scenario.summary),
            admin: scenario.admin ? clone(scenario.admin) : null,
            squadRelationOverride: scenario.me.squad_relation,
        };

        window.__previewAdmin = previewState.admin;

        const shell = window.AppShell;
        shell.me = previewState.me;
        shell.launch = previewState.launch;
        shell.squads = previewState.squads;
        shell.selectedGameId = previewState.me.default_game_id
            ?? previewState.squads.find((s) => s.id === (previewState.launch.squad_id || previewState.me.context_squad_id))?.games?.[0]?.id
            ?? null;
        shell.dockMode = false;

        updateToolbar();
    }

    function delay(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    window.__previewLoad = async function previewLoad() {
        await delay(300);
        applyScenario(currentScenarioId);
    };

    window.__previewApi = async function previewApi(path, options = {}) {
        await delay(200);

        if (!previewState) {
            applyScenario(currentScenarioId);
        }

        const method = (options.method || "GET").toUpperCase();
        const url = new URL(path, window.location.origin);
        const squadId = Number(url.searchParams.get("squad_id")) || previewState.me.primary_squad_id;
        const gameId = Number(url.searchParams.get("game_id")) || null;

        if (path === "/api/v1/me" && method === "GET") {
            return clone(previewState.me);
        }

        if (path === "/api/v1/squads" && method === "GET") {
            return clone(previewState.squads);
        }

        if (path === "/api/v1/games" && method === "GET") {
            return clone(previewState.games);
        }

        if (path === "/api/v1/me/primary-squad" && method === "PUT") {
            const body = JSON.parse(options.body || "{}");
            previewState.me.primary_squad_id = body.squad_id;
            previewState.me.context_squad_id = body.squad_id;
            const membership = previewState.me.memberships.find((m) => m.squad_id === body.squad_id);
            if (membership) {
                previewState.me.player = { ...membership };
            }
            return clone(previewState.me);
        }

        if (path.startsWith("/api/v1/attendances") && method === "GET") {
            let items = clone(previewState.attendances).map((item) => {
                const weeklyStatus = item.weekly_attend_status ?? null;
                let effectiveStatus = weeklyStatus;
                if (effectiveStatus == null && item.schedule_preset?.will_attend_default === true) {
                    effectiveStatus = "will_attend";
                }
                return {
                    ...item,
                    weekly_attend_status: weeklyStatus,
                    attend_status: effectiveStatus,
                };
            });
            if (gameId) {
                items = items.filter((item) => item.schedule_preset?.game?.id === gameId);
            }
            return items;
        }

        if (path.match(/\/api\/v1\/schedules\/\d+/) && method === "PUT") {
            const presetId = Number(path.split("/").pop().split("?")[0]);
            const body = JSON.parse(options.body || "{}");
            const item = previewState.attendances.find((entry) => entry.schedule_preset.id === presetId);
            if (item) {
                item.schedule_preset.will_attend_default = body.will_attend_default === true ? true : null;
                if (body.will_attend_default !== true) {
                    item.weekly_attend_status = null;
                    item.attend_status = null;
                } else {
                    item.weekly_attend_status = null;
                    item.attend_status = "will_attend";
                }
            }
            return null;
        }

        if (path.startsWith("/api/v1/attendance-summary") && method === "GET") {
            let items = clone(previewState.summary);
            if (gameId) {
                items = items.filter((item) => item.schedule_preset?.game?.id === gameId);
            }
            return items;
        }

        if (path.match(/\/api\/v1\/attendances\/\d+/) && method === "PUT") {
            const presetId = Number(path.split("/").pop().split("?")[0]);
            const body = JSON.parse(options.body || "{}");
            const item = previewState.attendances.find((entry) => entry.schedule_preset.id === presetId);
            if (item) {
                item.weekly_attend_status = body.attend_status;
                item.comment = body.comment;
                if (body.attend_status == null && item.schedule_preset?.will_attend_default === true) {
                    item.attend_status = "will_attend";
                } else {
                    item.attend_status = body.attend_status;
                }
            }
            return null;
        }

        if (path.match(/\/api\/v1\/squads\/\d+\/requests$/) && method === "POST") {
            previewState.me.squad_relation = "pending";
            return { id: 999, request_type: JSON.parse(options.body || "{}").request_type };
        }

        if (path.match(/^\/api\/v1\/player\/\d+$/) && method === "DELETE") {
            const squadId = Number(path.split("/").pop());
            previewState.me.memberships = previewState.me.memberships.filter(
                (membership) => membership.squad_id !== squadId
            );
            if (previewState.me.primary_squad_id === squadId) {
                const nextMembership = previewState.me.memberships.find((membership) => membership.squad_id != null);
                previewState.me.primary_squad_id = nextMembership?.squad_id ?? null;
                previewState.me.player = nextMembership ? { ...nextMembership } : previewState.me.player;
            }
            return null;
        }

        if (path.includes("/members") && method === "GET") {
            return clone(previewState.admin?.members || []);
        }
        if (path.includes("/friends") && method === "GET") {
            return clone(previewState.admin?.friends || []);
        }
        if (path.includes("/requests") && method === "GET") {
            return clone(previewState.admin?.requests || []);
        }
        if (path.includes("/blocked") && method === "GET") {
            return clone(previewState.admin?.blocked || []);
        }
        if (path.includes("/schedule-presets") && method === "GET") {
            return clone(previewState.admin?.schedulePresets || []);
        }
        if (path.includes("/schedule-presets") && method === "POST") {
            const body = JSON.parse(options.body || "{}");
            const preset = {
                id: Date.now(),
                title: body.title,
                recurrence_type: body.recurrence_type || "weekly",
                game_day_of_week: body.game_day_of_week ?? 0,
                day_of_month: body.day_of_month ?? null,
                recurrence_date: body.recurrence_date ?? null,
                game_time: `${body.game_time}:00`,
                game: body.game_id
                    ? previewState.games.find((game) => game.id === body.game_id) || null
                    : null,
            };
            previewState.admin = previewState.admin || {};
            previewState.admin.schedulePresets = [...(previewState.admin.schedulePresets || []), preset];
            return clone(preset);
        }
        if (path.match(/\/schedule-presets\/\d+$/) && method === "DELETE") {
            const presetId = Number(path.split("/").pop());
            previewState.admin.schedulePresets = (previewState.admin.schedulePresets || []).filter(
                (preset) => preset.id !== presetId
            );
            return null;
        }

        if (method === "POST" || method === "PUT" || method === "DELETE") {
            return null;
        }

        return [];
    };

    function updateToolbar() {
        const label = window.PREVIEW_SCENARIOS[currentScenarioId]?.label || "";
        const labelEl = document.querySelector("#preview-scenario-label");
        if (labelEl) {
            labelEl.textContent = label;
        }
        document.querySelectorAll(".preview-scenario-btn").forEach((button) => {
            button.classList.toggle("active", Number(button.dataset.scenario) === currentScenarioId);
        });
    }

    function buildToolbar() {
        const toolbar = document.createElement("div");
        toolbar.className = "preview-toolbar";
        toolbar.innerHTML = `
            <div class="preview-toolbar-inner">
                <div class="preview-scenario-buttons">
                    ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map((id) => `
                        <button type="button" class="preview-scenario-btn" data-scenario="${id}">${id}</button>
                    `).join("")}
                    <button type="button" class="preview-error-btn" id="preview-test-error">Err</button>
                </div>
                <p id="preview-scenario-label" class="preview-scenario-label"></p>
            </div>
        `;
        document.body.appendChild(toolbar);

        toolbar.querySelectorAll(".preview-scenario-btn").forEach((button) => {
            button.addEventListener("click", async () => {
                applyScenario(Number(button.dataset.scenario));
                window.AppShell.dockMode = false;
                window.AppShell.showHome();
                await window.AppShell.load();
            });
        });

        document.querySelector("#preview-test-error")?.addEventListener("click", () => {
            window.AppShell.showErrorToast({
                code: "access_denied",
                message: "Недостаточно прав.",
            });
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        buildToolbar();
        window.AppShell.load();
    });
})();
