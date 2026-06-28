const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
}

const loadingOverlay = document.querySelector("#loading-overlay");
const statusEl = document.querySelector("#status");
const statusMessageEl = document.querySelector("#status-message");
const statusActionEl = document.querySelector("#status-action");
const contextBanner = document.querySelector("#context-banner");
const identityBar = document.querySelector("#identity-bar");
const profileControls = document.querySelector("#profile-controls");
const gameSelectorEl = document.querySelector("#game-selector");
const mainMenu = document.querySelector("#main-menu");
const mainMenuGrid = document.querySelector("#main-menu-grid");
const viewHeader = document.querySelector("#view-header");
const viewTitle = document.querySelector("#view-title");
const backButton = document.querySelector("#back-button");
const registrationCard = document.querySelector("#registration-card");
const content = document.querySelector("#content");
const squadSearch = document.querySelector("#squad-search");
const squadList = document.querySelector("#squad-list");
const squadIdInput = document.querySelector("#squad-id");
const squadPicker = document.querySelector("#squad-picker");
const playerNameInput = document.querySelector("#player-name-input");
const registerButton = document.querySelector("#register-button");
const registrationTitle = document.querySelector("#registration-title");
const squadClear = document.querySelector("#squad-clear");
const attendanceTab = document.querySelector("#attendance-tab");
const summaryTab = document.querySelector("#summary-tab");
const adminTab = document.querySelector("#admin-tab");
const membersTab = document.querySelector("#members-tab");
const createSquadTab = document.querySelector("#create-squad-tab");
const createSquadForm = document.querySelector("#create-squad-form");
const createSquadSuccess = document.querySelector("#create-squad-success");
const confirmDialog = document.querySelector("#confirm-dialog");
const confirmDialogMessage = document.querySelector("#confirm-dialog-message");
const confirmDialogCancel = document.querySelector("#confirm-dialog-cancel");
const confirmDialogConfirm = document.querySelector("#confirm-dialog-confirm");
const confirmDialogBackdrop = confirmDialog?.querySelector(".confirm-dialog-backdrop");
const debugPanel = document.querySelector("#debug-panel");
const debugCodeInput = document.querySelector("#debug-code-input");
const debugUnlockButton = document.querySelector("#debug-unlock-button");
const debugLockButton = document.querySelector("#debug-lock-button");
const debugPanelClose = document.querySelector("#debug-panel-close");
const debugPanelUnlockSection = document.querySelector("#debug-panel-unlock");
const debugPanelActiveSection = document.querySelector("#debug-panel-active");

let confirmDialogResolve = null;

let me = null;
let launch = { source: "dm", squad_id: null };
let squads = [];
let games = [];
let squadListIndex = -1;
let loadingCount = 0;
let currentView = "home";
let selectedGameId = null;
let dockMode = false;
let dmActiveSquadId = null;
let personalMenuFromGroup = false;
let appScenario = null;
let scheduleWeekStart = null;

const dayNames = ["Пн.", "Вт.", "Ср.", "Чт.", "Пт.", "Сб.", "Вс."];
const dayNamesShort = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const monthNamesGenitive = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
];
const monthNamesNominative = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];
const recurrenceLabels = {
    weekly: "Еженедельно",
    monthly: "Ежемесячно",
    once: "Единоразово",
};
const statusLabels = {
    will_attend: "Приду",
    doubts: "Сомневаюсь",
    will_not_attend: "Не приду",
};

const authErrorMessages = {
    "Telegram auth data required": "Откройте приложение через кнопку в Telegram-боте.",
    "Invalid Telegram auth data": "Не удалось проверить авторизацию Telegram. Закройте приложение и откройте его снова из бота.",
    "Telegram auth data expired": "Сессия истекла. Закройте приложение и откройте его снова из бота.",
    access_denied: "Недостаточно прав.",
    cannot_remove_admin: "Нельзя удалить администратора Telegram-чата.",
    squad_blocked: "Доступ к этому отряду закрыт.",
    already_friend: "Вы уже друг этого отряда.",
    request_pending: "Заявка уже отправлена.",
    not_blocked: "Пользователь не заблокирован.",
    already_member: "Вы уже состоите в этом отряде.",
    squad_exists: "Отряд для этого чата уже создан.",
    game_has_dependencies: "Игра привязана к расписанию. Сначала отвяжите ее от связанных сущностей.",
    invalid_code: "Неверный код доступа.",
};

function getInitData() {
    return tg?.initData?.trim() || "";
}

const DEBUG_TOKEN_STORAGE_KEY = "arma_debug_token";
const DEBUG_NAME_TAP_TARGET = 10;
const DEBUG_NAME_TAP_RESET_MS = 3000;

let identityNameTapCount = 0;
let identityNameTapTimer = null;

function getStoredDebugToken() {
    try {
        return localStorage.getItem(DEBUG_TOKEN_STORAGE_KEY)?.trim() || "";
    } catch {
        return "";
    }
}

function setStoredDebugToken(token) {
    try {
        localStorage.setItem(DEBUG_TOKEN_STORAGE_KEY, token);
    } catch {
        // ignore storage errors
    }
}

function clearStoredDebugToken() {
    try {
        localStorage.removeItem(DEBUG_TOKEN_STORAGE_KEY);
    } catch {
        // ignore storage errors
    }
}

const TOAST_DURATION_MS = 5000;
const MAX_TOASTS = 4;

class ApiError extends Error {
    constructor(code, message, status) {
        super(message);
        this.name = "ApiError";
        this.code = code;
        this.status = status;
    }
}

function parseApiError(detail, status) {
    const code = typeof detail === "string"
        ? detail
        : (detail?.code || String(status));
    let message;
    if (typeof detail === "string" && authErrorMessages[detail]) {
        message = authErrorMessages[detail];
    } else if (typeof detail === "string") {
        message = detail;
    } else {
        message = detail?.message || detail?.msg || `Ошибка API: ${status}`;
    }
    return { code, message };
}

function formatApiError(detail, status) {
    return parseApiError(detail, status).message;
}

function getToastContainer() {
    let container = document.querySelector("#toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container";
        container.setAttribute("aria-live", "polite");
        document.body.appendChild(container);
    }
    return container;
}

function dismissToast(toast) {
    if (!toast.isConnected) {
        return;
    }
    toast.classList.add("toast-hiding");
    const remove = () => toast.remove();
    toast.addEventListener("transitionend", remove, { once: true });
    setTimeout(remove, 350);
}

function closeConfirmDialog(result) {
    if (!confirmDialog) {
        return;
    }
    confirmDialog.classList.add("hidden");
    const resolve = confirmDialogResolve;
    confirmDialogResolve = null;
    resolve?.(result);
}

function showConfirmDialog({
    message,
    confirmLabel = "Подтвердить",
    cancelLabel = "Отмена",
    danger = false,
}) {
    if (!confirmDialog || !confirmDialogMessage) {
        return Promise.resolve(window.confirm(message));
    }

    closeConfirmDialog(false);

    confirmDialogMessage.textContent = message;
    confirmDialogConfirm.textContent = confirmLabel;
    confirmDialogCancel.textContent = cancelLabel;
    confirmDialogConfirm.className = danger ? "danger-button" : "menu-button";

    return new Promise((resolve) => {
        confirmDialogResolve = resolve;
        confirmDialog.classList.remove("hidden");
        confirmDialogCancel.focus();
    });
}

function setupConfirmDialog() {
    if (!confirmDialog) {
        return;
    }
    confirmDialogCancel?.addEventListener("click", () => closeConfirmDialog(false));
    confirmDialogConfirm?.addEventListener("click", () => closeConfirmDialog(true));
    confirmDialogBackdrop?.addEventListener("click", () => closeConfirmDialog(false));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && confirmDialogResolve != null) {
            closeConfirmDialog(false);
        }
    });
}

setupConfirmDialog();

function showErrorToast(error, fallbackMessage) {
    let code = "error";
    let message = fallbackMessage || "Неизвестная ошибка";

    if (error instanceof ApiError) {
        code = error.code;
        message = error.message;
    } else if (error && typeof error === "object" && "code" in error && "message" in error) {
        code = String(error.code);
        message = String(error.message);
    } else if (typeof error === "string") {
        code = authErrorMessages[error] ? error : "client";
        message = authErrorMessages[error] || error;
    } else if (error?.message) {
        code = error.code ? String(error.code) : "client";
        message = error.message;
    }

    const container = getToastContainer();
    while (container.children.length >= MAX_TOASTS) {
        container.firstElementChild?.remove();
    }

    const toast = document.createElement("div");
    toast.className = "toast toast-error";
    toast.setAttribute("role", "alert");
    toast.innerHTML = `
        <p class="toast-code">${escapeHtml(code)}</p>
        <p class="toast-message">${escapeHtml(message)}</p>
    `;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("toast-visible"));

    const timer = setTimeout(() => dismissToast(toast), TOAST_DURATION_MS);
    toast.addEventListener("click", () => {
        clearTimeout(timer);
        dismissToast(toast);
    });
}

function setStatus(message, isError = false, action = null) {
    if (isError) {
        showErrorToast(message);
        return;
    }

    if (statusMessageEl) {
        statusMessageEl.textContent = message;
    } else {
        statusEl.textContent = message;
    }

    if (statusActionEl) {
        if (action?.label && action?.onClick) {
            statusActionEl.textContent = action.label;
            statusActionEl.classList.remove("hidden");
            statusActionEl.onclick = () => {
                action.onClick();
                statusActionEl.classList.add("hidden");
                statusActionEl.onclick = null;
            };
        } else {
            statusActionEl.classList.add("hidden");
            statusActionEl.onclick = null;
        }
    }

    statusEl.classList.remove("error");
    statusEl.classList.remove("hidden");
}

function hideStatus() {
    statusEl.classList.add("hidden");
    statusEl.classList.remove("error");
    if (statusActionEl) {
        statusActionEl.classList.add("hidden");
        statusActionEl.onclick = null;
    }
}

function setLoading(active) {
    loadingCount += active ? 1 : -1;
    if (loadingCount < 0) {
        loadingCount = 0;
    }

    loadingOverlay.classList.toggle("hidden", loadingCount === 0);
    loadingOverlay.setAttribute("aria-busy", loadingCount > 0 ? "true" : "false");
}

function squadMemberships() {
    return (me?.memberships || []).filter((membership) => membership.squad_id != null);
}

function hasSoloMembership() {
    return (me?.memberships || []).some((membership) => membership.squad_id == null);
}

function isSoloOnly() {
    return hasSoloMembership() && !squadMemberships().length;
}

function isSquadChatLaunch() {
    return launch?.source === "squad_chat" && launch?.squad_id != null;
}

function isPersonalLaunch() {
    return !isSquadChatLaunch();
}

function isGroupChatLaunch() {
    return launch?.source === "squad_chat";
}

function isPersonalMenuActive() {
    return isPersonalLaunch() || personalMenuFromGroup;
}

function resolveLaunchContext(serverMe) {
    const unsafe = tg?.initDataUnsafe || {};
    const chatType = unsafe.chat_type || "";

    if (["group", "supergroup", "channel"].includes(chatType)) {
        return {
            source: "squad_chat",
            squad_id: serverMe?.launch_squad_id ?? null,
        };
    }

    if (["private", "sender"].includes(chatType) || !chatType) {
        return { source: "dm", squad_id: null };
    }

    if (serverMe?.launch_source === "squad_chat" && serverMe?.launch_squad_id != null) {
        return {
            source: "squad_chat",
            squad_id: serverMe.launch_squad_id,
        };
    }

    return { source: "dm", squad_id: null };
}

function isDmLaunch() {
    return isPersonalLaunch();
}

function shouldUseForeignSoloMenu() {
    if (me?.is_debug_admin) {
        return false;
    }
    if (!isForeignChatContext() || dockMode) {
        return false;
    }
    return me?.squad_relation !== "member";
}

function shouldUseSoloMenuInContext() {
    if (me?.is_debug_admin && (contextSquadId() != null || launch?.squad_id != null)) {
        return false;
    }
    return isSoloOnly() || shouldUseForeignSoloMenu();
}

function isDebugAdminActive() {
    return Boolean(me?.is_debug_admin);
}

function blocksForeignMenu() {
    return isForeignChatContext() && !dockMode && !isDebugAdminActive();
}

function shouldShowDmSquadPicker() {
    if (!isPersonalMenuActive() || currentView !== "home" || dmActiveSquadId != null) {
        return false;
    }
    if (isDebugAdminActive()) {
        return squads.length > 0;
    }
    return squadMemberships().length > 0;
}

function isSoloGroupAdminNoSquad() {
    return isSoloOnly() && Boolean(me?.can_create_squad);
}

function isRegistered() {
    return Boolean(me?.memberships?.length);
}

function getSquadById(squadId) {
    return squads.find((entry) => entry.id === squadId) || null;
}

function contextSquadId() {
    if (dockMode && me?.primary_squad_id) {
        return me.primary_squad_id;
    }
    if (isPersonalMenuActive() && dmActiveSquadId != null) {
        return dmActiveSquadId;
    }
    return me?.context_squad_id
        ?? (launch?.source === "squad_chat" ? launch?.squad_id : null)
        ?? me?.primary_squad_id
        ?? null;
}

function ownSquadId() {
    return me?.primary_squad_id ?? squadMemberships()[0]?.squad_id ?? null;
}

function isForeignChatContext() {
    if (launch?.source !== "squad_chat" || !launch?.squad_id) {
        return false;
    }
    const own = ownSquadId();
    return own != null && launch.squad_id !== own;
}

function resolveAppScenario(currentMe, currentLaunch) {
    const soloOnly = (currentMe?.memberships || []).some((m) => m.squad_id == null)
        && !(currentMe?.memberships || []).some((m) => m.squad_id != null);
    const hasMember = (currentMe?.memberships || []).some((m) => m.squad_id != null);
    const inChat = currentLaunch?.source === "squad_chat" && currentLaunch?.squad_id;
    const adminSquadId = resolveAdminSquadId(currentMe);
    const isAdmin = adminSquadId != null;

    if (soloOnly) {
        if (inChat && currentMe?.is_debug_admin && currentLaunch?.squad_id) {
            return 7;
        }
        return inChat ? 2 : 1;
    }

    if (!hasMember) {
        return 1;
    }

    if (inChat) {
        const own = currentMe?.primary_squad_id ?? squadMemberships()[0]?.squad_id;
        const foreign = own != null && currentLaunch.squad_id !== own;
        if (foreign) {
            if (currentMe?.is_debug_admin) {
                return 7;
            }
            return isAdmin ? 6 : 5;
        }
        return isAdmin ? 7 : 4;
    }

    return isAdmin ? 8 : 3;
}

function getPlayerDisplayName() {
    if (!me?.memberships?.length) {
        return "";
    }
    return me.player?.name
        || me.memberships.find((m) => m.squad_id == null)?.name
        || me.memberships[0]?.name
        || "";
}

const IDENTITY_DASH = "&nbsp;—&nbsp;";

function isEffectiveSquadAdmin(squadId = null) {
    if (me?.is_debug_admin) {
        if (squadId != null) {
            return true;
        }
        return contextSquadId() != null || launch?.squad_id != null;
    }
    if (squadId != null) {
        return me?.is_admin_of_squad_id === squadId
            || (Boolean(me?.is_squad_admin) && me?.primary_squad_id === squadId);
    }
    return Boolean(me?.is_admin_of_squad_id || me?.is_squad_admin);
}

function resolveAdminSquadId(currentMe = me) {
    if (currentMe?.is_admin_of_squad_id != null) {
        return currentMe.is_admin_of_squad_id;
    }
    if (currentMe?.is_squad_admin && currentMe?.primary_squad_id != null) {
        return currentMe.primary_squad_id;
    }
    if (currentMe?.is_debug_admin) {
        if (currentMe?.context_squad_id != null) {
            return currentMe.context_squad_id;
        }
        if (launch?.squad_id != null) {
            return launch.squad_id;
        }
        const firstMembership = (currentMe?.memberships || []).find((membership) => membership.squad_id != null);
        return firstMembership?.squad_id ?? null;
    }
    return null;
}

function buildIdentitySquadText() {
    if (!me?.memberships?.length) {
        return "";
    }

    const squadParts = [];
    const primaryId = me.primary_squad_id;
    const squadMs = squadMemberships();

    if (squadMs.length) {
        const primary = squadMs.find((m) => m.squad_id === primaryId) || squadMs[0];
        squadParts.push(primary.squad_name || "Отряд");
        squadMs
            .filter((m) => m.squad_id !== primary.squad_id)
            .forEach((m) => squadParts.push(m.squad_name || "Отряд"));
    } else if (me.squad_relation === "friend") {
        const contextSquad = getSquadById(contextSquadId());
        squadParts.push(contextSquad?.name ? `${contextSquad.name} (друг)` : "друг отряда");
    } else if (hasSoloMembership()) {
        squadParts.push("Одиночка");
    }

    return squadParts.join(" / ");
}

function buildIdentityText() {
    const squadText = buildIdentitySquadText();
    const playerName = getPlayerDisplayName();
    if (!squadText && !playerName) {
        return "";
    }
    if (!squadText) {
        return playerName;
    }
    if (!playerName) {
        return squadText;
    }
    return `${squadText} — ${playerName}`;
}

function buildIdentityNameElementHtml(playerName) {
    if (!playerName) {
        return "";
    }
    return `<span class="identity-player-name">${escapeHtml(playerName)}</span>`;
}

function buildIdentityContentHtml() {
    const squadText = buildIdentitySquadText();
    const playerName = getPlayerDisplayName();
    if (!squadText && !playerName) {
        return "";
    }
    if (!squadText) {
        return buildIdentityNameElementHtml(playerName);
    }
    if (!playerName) {
        return escapeHtml(squadText);
    }
    return `${escapeHtml(squadText)}${IDENTITY_DASH}${buildIdentityNameElementHtml(playerName)}`;
}

function debugBadgeHtml() {
    return me?.is_debug_admin ? '<span class="debug-badge" title="Режим отладки">DEBUG</span>' : "";
}

function onIdentityNameTap() {
    identityNameTapCount += 1;
    clearTimeout(identityNameTapTimer);
    identityNameTapTimer = setTimeout(() => {
        identityNameTapCount = 0;
    }, DEBUG_NAME_TAP_RESET_MS);
    if (identityNameTapCount >= DEBUG_NAME_TAP_TARGET) {
        identityNameTapCount = 0;
        openDebugPanel();
    }
}

function setupIdentityNameEasterEgg() {
    if (!identityBar || identityBar.dataset.debugTapSetup === "1") {
        return;
    }
    identityBar.dataset.debugTapSetup = "1";
    identityBar.addEventListener("pointerup", (event) => {
        if (!event.target.closest(".identity-player-name")) {
            return;
        }
        onIdentityNameTap(event);
    });
}

function updateDebugPanelState() {
    const isActive = Boolean(me?.is_debug_admin);
    debugPanelUnlockSection?.classList.toggle("hidden", isActive);
    debugPanelActiveSection?.classList.toggle("hidden", !isActive);
}

function openDebugPanel() {
    if (!debugPanel) {
        return;
    }
    updateDebugPanelState();
    debugPanel.classList.remove("hidden");
    debugCodeInput?.focus();
}

function closeDebugPanel() {
    debugPanel?.classList.add("hidden");
    if (debugCodeInput) {
        debugCodeInput.value = "";
    }
}

async function unlockDebugMode() {
    const code = debugCodeInput?.value?.trim();
    if (!code) {
        setStatus("Введите код доступа.", true);
        return;
    }

    try {
        const result = await api("/api/v1/debug/unlock", {
            method: "POST",
            body: JSON.stringify({ code }),
        });
        setStoredDebugToken(result.token);
        me = await api("/api/v1/me");
        squads = await api("/api/v1/squads");
        appScenario = resolveAppScenario(me, launch);
        updateDebugPanelState();
        renderShell();
        closeDebugPanel();
        setStatus("Режим отладки включён.");
    } catch (error) {
        showErrorToast(error);
    }
}

async function lockDebugMode() {
    clearStoredDebugToken();
    try {
        await api("/api/v1/debug/lock", { method: "POST" });
    } catch {
        // local token already cleared
    }
    me = await api("/api/v1/me");
    appScenario = resolveAppScenario(me, launch);
    updateDebugPanelState();
    renderShell();
    closeDebugPanel();
    setStatus("Режим отладки отключён.");
}

const IDENTITY_GEAR_ICON = `
    <svg class="identity-settings-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <path fill="currentColor" d="M12 15.5A3.5 3.5 0 0 1 8.5 12 3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5 3.5 3.5 0 0 1-3.5 3.5m7.43-2.53c.04-.32.07-.64.07-.97 0-.33-.03-.66-.07-1l2.11-1.63c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.31-.61-.22l-2.49 1c-.52-.39-1.06-.73-1.69-.98l-.37-2.65A.506.506 0 0 0 14 2h-4c-.25 0-.46.18-.5.42l-.37 2.65c-.63.25-1.17.59-1.69.98l-2.49-1c-.22-.09-.49 0-.61.22l-2 3.46c-.12.22-.07.49.12.64L4.57 11c-.04.34-.07.67-.07 1 0 .33.03.65.07.97l-2.11 1.66c-.19.15-.25.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1.01c.52.4 1.06.74 1.69.99l.37 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.37-2.65c.63-.26 1.17-.59 1.69-.99l2.49 1.01c.22.08.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.66z"/>
    </svg>
`;

async function saveIdentityNameInput(input) {
    const nextName = input.value.trim();
    const prevName = getPlayerDisplayName();
    if (!nextName) {
        input.value = prevName;
        setStatus("Введите игровой ник.", true);
        return;
    }
    if (nextName === prevName) {
        return;
    }
    try {
        me = await api("/api/v1/me/player-name", {
            method: "PUT",
            body: JSON.stringify({ name: nextName }),
        });
        appScenario = resolveAppScenario(me, launch);
        renderShell();
        setStatus("Ник обновлён.");
    } catch (error) {
        input.value = prevName;
        showErrorToast(error);
    }
}

function bindIdentityNameInput(input) {
    if (!input || input.dataset.bound === "1") {
        return;
    }
    input.dataset.bound = "1";
    input.addEventListener("blur", () => {
        void saveIdentityNameInput(input);
    });
    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            input.blur();
        }
    });
}

function renderIdentityBar() {
    if (!identityBar) {
        return;
    }

    const squadText = buildIdentitySquadText();
    const playerName = getPlayerDisplayName();
    if ((!squadText && !playerName) || !isRegistered()) {
        identityBar.classList.add("hidden");
        identityBar.innerHTML = "";
        return;
    }

    const existingInput = identityBar.querySelector(".identity-name-input");
    const isEditing = existingInput && document.activeElement === existingInput;

    if (isPersonalMenuActive()) {
        if (isEditing) {
            const squadEl = identityBar.querySelector(".identity-squads");
            const lineEl = identityBar.querySelector(".identity-line");
            if (lineEl && !squadEl) {
                const input = lineEl.querySelector(".identity-name-input");
                const playerName = input?.value || getPlayerDisplayName();
                lineEl.innerHTML = `${escapeHtml(squadText)}${IDENTITY_DASH}<input
                    class="identity-name-input identity-player-name"
                    type="text"
                    maxlength="50"
                    value="${escapeHtml(playerName)}"
                    autocomplete="off"
                    spellcheck="false"
                    aria-label="Игровой ник"
                >`;
                const nextInput = lineEl.querySelector(".identity-name-input");
                bindIdentityNameInput(nextInput);
                if (nextInput) {
                    nextInput.focus();
                    const end = nextInput.value.length;
                    nextInput.setSelectionRange(end, end);
                }
            } else if (squadEl) {
                squadEl.textContent = squadText;
            }
            identityBar.classList.remove("hidden");
            return;
        }

        identityBar.className = "identity-bar identity-bar--personal";
        identityBar.innerHTML = `
            <div class="identity-bar-inner identity-bar-inner--personal">
                <span class="identity-line">${escapeHtml(squadText)}${IDENTITY_DASH}<input
                    class="identity-name-input identity-player-name"
                    type="text"
                    maxlength="50"
                    value="${escapeHtml(playerName)}"
                    autocomplete="off"
                    spellcheck="false"
                    aria-label="Игровой ник"
                ></span>${debugBadgeHtml()}
            </div>
        `;
        bindIdentityNameInput(identityBar.querySelector(".identity-name-input"));
        identityBar.classList.remove("hidden");
        return;
    }

    if (isGroupChatLaunch()) {
        identityBar.className = "identity-bar identity-bar--group";
        identityBar.innerHTML = `
            <div class="identity-bar-inner identity-bar-inner--group">
                <span class="identity-text">${buildIdentityContentHtml()}${debugBadgeHtml()}</span>
                <button
                    class="identity-settings-button"
                    type="button"
                    aria-label="Личное меню"
                    title="Личное меню"
                >${IDENTITY_GEAR_ICON}</button>
            </div>
        `;
        identityBar.querySelector(".identity-settings-button")?.addEventListener("click", () => {
            personalMenuFromGroup = true;
            dmActiveSquadId = null;
            renderShell();
        });
        identityBar.classList.remove("hidden");
        return;
    }

    identityBar.className = "identity-bar";
    identityBar.innerHTML = `<div class="identity-bar-inner"><span class="identity-text">${buildIdentityContentHtml()}${debugBadgeHtml()}</span></div>`;
    identityBar.classList.remove("hidden");
}

function renderContextBanner() {
    if (!isRegistered()) {
        contextBanner.classList.add("hidden");
        return;
    }

    let text = "";
    let variant = "info";

    if (launch?.source === "squad_chat" && launch?.squad_id) {
        const squad = getSquadById(launch.squad_id);
        const name = squad?.name || "Отряд";
        const own = ownSquadId();
        const relation = me?.squad_relation;
        const inThisSquadContext = contextSquadId() === launch.squad_id;

        if (own != null && launch.squad_id === own) {
            if (isEffectiveSquadAdmin()) {
                text = `Открыто из чата отряда «${name}» · вы администратор`;
                variant = "own";
            } else {
                text = `Открыто из чата отряда «${name}» · ваш отряд`;
                variant = "own";
            }
        } else if (relation === "friend" && inThisSquadContext) {
            text = `Открыто из чата отряда «${name}» · друг отряда`;
            variant = "own";
        } else if (relation === "pending" && inThisSquadContext) {
            text = `Открыто из чата отряда «${name}» · заявка на рассмотрении`;
            variant = "info";
        } else if (relation === "blocked" && inThisSquadContext) {
            text = `Открыто из чата отряда «${name}» · доступ закрыт`;
            variant = "foreign";
        } else {
            text = `Открыто из чата отряда «${name}» · чужой отряд`;
            variant = "foreign";
        }
    } else if (launch?.source === "squad_chat") {
        if (me?.can_create_squad) {
            text = "Групповой чат · вы администратор";
            variant = "own";
        } else {
            text = "Групповой чат";
            variant = "info";
        }
    } else {
        text = "Личные сообщения";
        variant = "info";
    }

    contextBanner.textContent = text;
    contextBanner.className = `context-banner context-banner--${variant}`;
    contextBanner.classList.remove("hidden");
}

function renderPrimarySelectorHtml() {
    if (shouldUseForeignSoloMenu()) {
        return "";
    }
    const memberships = squadMemberships();
    if (memberships.length < 2) {
        return "";
    }

    return `
        <div class="primary-squad-picker">
            <p class="memberships-label">Основной отряд</p>
            <div class="segmented">
                ${memberships.map((membership) => `
                    <button
                        class="primary-squad-option ${membership.squad_id === me.primary_squad_id ? "active" : ""}"
                        data-squad-id="${membership.squad_id}"
                        type="button"
                    >${escapeHtml(membership.squad_name || "Отряд")}</button>
                `).join("")}
            </div>
        </div>
    `;
}

function renderOwnSquadDock() {
    if (shouldUseForeignSoloMenu() || shouldShowDmSquadPicker()) {
        return "";
    }
    if (![5, 6].includes(appScenario) || dockMode) {
        return "";
    }

    const ownId = ownSquadId();
    const ownSquad = getSquadById(ownId);
    if (!ownSquad) {
        return "";
    }

    const isAdmin = isEffectiveSquadAdmin();
    const pending = window.__previewAdmin?.pendingCount;

    if (isAdmin) {
        return `
            <div class="own-squad-dock own-squad-dock--admin">
                <p class="own-squad-dock-title">Ваш отряд: ${escapeHtml(ownSquad.name)} <span class="admin-badge">админ</span></p>
                ${pending != null ? `<p class="own-squad-dock-meta">Заявок: ${pending}</p>` : ""}
                <div class="dock-actions">
                    <button class="ghost-button dock-button" type="button" data-dock-view="attendance">Расписание</button>
                    <button class="ghost-button dock-button" type="button" data-dock-view="summary">Отряд</button>
                    <button class="ghost-button dock-button" type="button" data-dock-view="members">Участники</button>
                    <button class="ghost-button dock-button" type="button" data-dock-view="admin">Управление</button>
                </div>
            </div>
        `;
    }

    return `
        <div class="own-squad-dock">
            <p class="own-squad-dock-title">Ваш отряд: ${escapeHtml(ownSquad.name)}</p>
            <div class="dock-actions">
                <button class="ghost-button dock-button" type="button" data-dock-view="attendance">Расписание · ${escapeHtml(ownSquad.name)}</button>
                <button class="ghost-button dock-button" type="button" data-dock-view="summary">Отряд · ${escapeHtml(ownSquad.name)}</button>
                <button class="ghost-button dock-button" type="button" data-dock-view="members">Участники · ${escapeHtml(ownSquad.name)}</button>
            </div>
        </div>
    `;
}

function bindProfileControls() {
    profileControls.querySelectorAll(".primary-squad-option").forEach((button) => {
        button.addEventListener("click", async () => {
            const squadId = Number(button.dataset.squadId);
            if (squadId === me.primary_squad_id) {
                return;
            }
            try {
                me = await api("/api/v1/me/primary-squad", {
                    method: "PUT",
                    body: JSON.stringify({ squad_id: squadId }),
                });
                dockMode = false;
                appScenario = resolveAppScenario(me, launch);
                renderShell();
            } catch (error) {
                showErrorToast(error);
            }
        });
    });

    profileControls.querySelectorAll(".dock-button").forEach((button) => {
        button.addEventListener("click", () => {
            dockMode = true;
            const view = button.dataset.dockView;
            if (selectedGameId == null) {
                const squad = getSquadById(ownSquadId());
                selectedGameId = squad?.games?.[0]?.id ?? null;
            }
            showView(view);
        });
    });
}

function renderProfileControls() {
    if (!isRegistered() || shouldShowDmSquadPicker()) {
        profileControls.classList.add("hidden");
        profileControls.innerHTML = "";
        return;
    }

    const html = renderPrimarySelectorHtml() + renderOwnSquadDock();
    if (!html) {
        profileControls.classList.add("hidden");
        profileControls.innerHTML = "";
        return;
    }

    profileControls.innerHTML = html;
    profileControls.classList.remove("hidden");
    bindProfileControls();
}

function squadGamesForContext() {
    const squadId = dockMode ? ownSquadId() : contextSquadId();
    const squad = getSquadById(squadId);
    return squad?.games || [];
}

function defaultGameIdForContext() {
    const squadId = dockMode ? ownSquadId() : contextSquadId();
    const squad = getSquadById(squadId);
    const mainGameId = squad?.main_game_ids?.[0];
    if (mainGameId != null && squad?.games?.some((game) => game.id === mainGameId)) {
        return mainGameId;
    }
    return squad?.games?.[0]?.id ?? null;
}

function renderGameSelector() {
    const squadGames = squadGamesForContext();
    const squadId = dockMode ? ownSquadId() : contextSquadId();

    if (!squadId || !squadGames.length) {
        gameSelectorEl.classList.add("hidden");
        gameSelectorEl.innerHTML = "";
        return;
    }

    if (selectedGameId == null || !squadGames.some((g) => g.id === selectedGameId)) {
        selectedGameId = defaultGameIdForContext();
    }

    gameSelectorEl.innerHTML = `
        <p class="memberships-label">Игра</p>
        <div class="segmented game-options">
            ${squadGames.map((game) => `
                <button
                    class="game-option ${game.id === selectedGameId ? "active" : ""}"
                    data-game-id="${game.id}"
                    type="button"
                >${escapeHtml(game.title)}</button>
            `).join("")}
        </div>
    `;
    gameSelectorEl.classList.remove("hidden");

    gameSelectorEl.querySelectorAll(".game-option").forEach((button) => {
        button.addEventListener("click", () => {
            selectedGameId = Number(button.dataset.gameId);
            renderGameSelector();
            if (currentView === "attendance") {
                void renderAttendances();
            } else if (currentView === "summary") {
                renderSummary();
            }
        });
    });
}

function shouldUseGroupMenuForSquad(squadId) {
    return isGroupChatLaunch()
        && launch?.squad_id != null
        && squadId === launch.squad_id;
}

function menuItemConfig() {
    const relation = me?.squad_relation;
    const inPersonalSquadPick = isPersonalMenuActive() && dmActiveSquadId != null;
    const inForeign = blocksForeignMenu() && !inPersonalSquadPick;
    const hasContext = contextSquadId() != null;
    const canScheduleMember = relation === "member" || relation === "friend" || isDebugAdminActive();
    const isAdmin = isEffectiveSquadAdmin();
    const dmSquadId = isPersonalMenuActive() ? dmActiveSquadId : null;
    const dmIsAdmin = dmSquadId != null && isEffectiveSquadAdmin(dmSquadId);

    if (shouldUseSoloMenuInContext()) {
        const noContext = !hasContext;
        const soloGroupAdmin = isSoloGroupAdminNoSquad();
        const noContextHint = "Откройте приложение из чата отряда";
        const pending = relation === "pending";
        const blocked = relation === "blocked";
        const isFriend = relation === "friend";
        const isOutsider = hasContext && !pending && !blocked && !isFriend && relation !== "member";
        const friendRequestDisabled = noContext || pending || blocked || isFriend || relation === "member";
        const joinRequestDisabled = noContext || pending || blocked || relation === "member";

        const items = [
            {
                id: "attendance",
                label: "Расписание",
                view: "attendance",
                disabled: noContext,
                hint: noContext
                    ? noContextHint
                    : isOutsider
                        ? "Только просмотр"
                        : isFriend
                            ? "Друг отряда"
                            : "",
            },
        ];

        if (canScheduleMember) {
            items.push({
                id: "summary",
                label: "Посещаемость",
                view: "summary",
                disabled: noContext,
                hint: noContext ? noContextHint : "",
            });
        }

        if (isFriend) {
            items.push({
                id: "members",
                label: "Участники",
                view: "members",
                disabled: noContext,
                hint: noContext ? noContextHint : "",
            });
        }

        if (!isFriend) {
            items.push({
                id: "request-friend",
                label: "Запросить дружбу с отрядом",
                action: "request-friend",
                disabled: friendRequestDisabled,
                hint: noContext
                    ? noContextHint
                    : pending
                        ? "Заявка на рассмотрении"
                        : blocked
                            ? "Доступ закрыт"
                            : isOutsider
                                ? "Смотреть расписание и отмечаться на играх"
                                : "",
            });
        }

        items.push({
            id: "request-join",
            label: "Запросить вступление в отряд",
            action: "request-join",
            disabled: joinRequestDisabled,
            hint: noContext
                ? noContextHint
                : pending
                    ? "Заявка на рассмотрении"
                    : blocked
                        ? "Доступ закрыт"
                        : isFriend || isOutsider
                            ? "Стать участником отряда"
                            : "",
        });

        if (isFriend) {
            items.push({
                id: "leave-squad",
                label: "Выйти из отряда",
                action: "leave-friendship",
                disabled: noContext,
                hint: noContext ? noContextHint : "",
            });
        }

        if (soloGroupAdmin) {
            items.unshift({
                id: "create-squad",
                label: "Создать отряд",
                view: "create-squad",
                disabled: false,
                hint: "",
            });
        }

        return {
            type: "solo",
            items,
        };
    }

    const items = [
        {
            id: "attendance",
            label: "Расписание",
            view: "attendance",
            disabled: dmSquadId == null ? (inForeign || !canScheduleMember) : false,
            hint: dmSquadId != null ? "" : (inForeign ? "Используйте блок «Ваш отряд»" : ""),
        },
        {
            id: "summary",
            label: "Посещаемость",
            view: "summary",
            disabled: dmSquadId == null ? (inForeign || !canScheduleMember) : false,
            hint: dmSquadId != null ? "" : (inForeign ? "Используйте блок «Ваш отряд»" : ""),
        },
        {
            id: "members",
            label: "Участники",
            view: "members",
            disabled: dmSquadId == null
                ? (inForeign || (!isDebugAdminActive() && !squadMemberships().length))
                : false,
            hint: dmSquadId != null ? "" : (inForeign ? "Используйте блок «Ваш отряд»" : ""),
        },
    ];

    const showAdmin = inForeign ? false : (dmSquadId != null ? dmIsAdmin : isAdmin);
    if (showAdmin) {
        items.push({
            id: "admin",
            label: "Управление отрядом",
            view: "admin",
            disabled: false,
            hint: "",
        });
    }

    return { type: "member", items };
}

function renderDmSquadPickerCard(squadId, squadName, options = {}) {
    const { showLeave = false, launchBadge = false } = options;
    const leaveButton = showLeave
        ? `<button
                class="ghost-button membership-leave dm-squad-leave dm-squad-leave-icon"
                type="button"
                data-squad-id="${squadId}"
                title="Выйти"
                aria-label="Выйти из отряда"
            ><span aria-hidden="true">✕</span></button>`
        : "";

    return `
        <div class="dm-squad-card">
            <p class="dm-squad-card-name">
                ${escapeHtml(squadName || "Отряд")}
                ${launchBadge ? '<span class="admin-badge">чат</span>' : ""}
            </p>
            <div class="dm-squad-card-actions">
                <div class="dm-squad-split-button${showLeave ? "" : " dm-squad-split-button--solo"}">
                    <button
                        class="menu-button dm-squad-open"
                        type="button"
                        data-squad-id="${squadId}"
                    >Открыть</button>
                    ${leaveButton}
                </div>
            </div>
        </div>
    `;
}

function renderDmSquadPickerHtml() {
    if (isDebugAdminActive()) {
        const entries = [...squads].sort((left, right) => (left.name || "").localeCompare(right.name || "", "ru"));
        if (!entries.length) {
            return "";
        }

        return `
            <div class="dm-squad-picker">
                <p class="memberships-label">Все отряды</p>
                <div class="dm-squad-cards">
                    ${entries.map((squad) => {
                        const membership = squadMemberships().find((entry) => entry.squad_id === squad.id);
                        return renderDmSquadPickerCard(squad.id, squad.name, {
                            showLeave: Boolean(membership),
                            launchBadge: isGroupChatLaunch() && launch?.squad_id === squad.id,
                        });
                    }).join("")}
                </div>
            </div>
        `;
    }

    const memberships = squadMemberships();
    if (!memberships.length) {
        return "";
    }

    return `
        <div class="dm-squad-picker">
            <p class="memberships-label">Мои отряды</p>
            <div class="dm-squad-cards">
                ${memberships.map((membership) => renderDmSquadPickerCard(
                    membership.squad_id,
                    membership.squad_name,
                    { showLeave: true },
                )).join("")}
            </div>
        </div>
    `;
}

function bindDmSquadPicker() {
    mainMenuGrid.querySelectorAll(".dm-squad-open").forEach((button) => {
        button.addEventListener("click", () => {
            const squadId = Number(button.dataset.squadId);
            if (personalMenuFromGroup && shouldUseGroupMenuForSquad(squadId) && !isDebugAdminActive()) {
                personalMenuFromGroup = false;
                dmActiveSquadId = null;
            } else {
                dmActiveSquadId = squadId;
            }
            selectedGameId = null;
            renderShell();
        });
    });

    mainMenuGrid.querySelectorAll(".dm-squad-leave").forEach((button) => {
        button.addEventListener("click", async () => {
            const squadId = Number(button.dataset.squadId);
            const membership = squadMemberships().find((entry) => entry.squad_id === squadId);
            const squadName = membership?.squad_name || "отряд";
            const confirmed = await showConfirmDialog({
                message: `Покинуть отряд «${squadName}»?`,
                confirmLabel: "Покинуть",
                cancelLabel: "Отмена",
                danger: true,
            });
            if (!confirmed) {
                return;
            }
            try {
                await api(`/api/v1/player/${squadId}`, { method: "DELETE" });
                if (dmActiveSquadId === squadId) {
                    dmActiveSquadId = null;
                }
                me = await api("/api/v1/me");
                appScenario = resolveAppScenario(me, launch);
                if (!squadMemberships().length && !hasSoloMembership()) {
                    currentView = "home";
                    syncViewChrome();
                    await renderRegistration();
                    return;
                }
                renderShell();
                setStatus("Вы покинули отряд.");
            } catch (error) {
                showErrorToast(error);
            }
        });
    });
}

function renderMainMenu() {
    if (currentView !== "home") {
        mainMenu.classList.add("hidden");
        return;
    }

    if (!isRegistered()) {
        mainMenu.classList.add("hidden");
        return;
    }

    const inForeign = isForeignChatContext() && !dockMode;
    if (inForeign && appScenario === 6 && !shouldUseForeignSoloMenu() && !isDebugAdminActive()) {
        mainMenu.classList.add("hidden");
        return;
    }

    if (shouldShowDmSquadPicker()) {
        mainMenuGrid.className = "menu-grid dm-squad-grid";
        mainMenuGrid.innerHTML = renderDmSquadPickerHtml();
        bindDmSquadPicker();
        mainMenu.classList.remove("hidden");
        return;
    }

    const { type, items } = menuItemConfig();
    const squadMemberMenu = type === "member";
    mainMenuGrid.className = type === "solo"
        ? "menu-grid menu-grid--solo"
        : squadMemberMenu
            ? "menu-grid menu-grid--squad"
            : "menu-grid";

    const groupMenuBack = personalMenuFromGroup && isGroupChatLaunch() && dmActiveSquadId != null
        ? `<button class="ghost-button dm-squad-back" type="button" data-action="group-menu-back">← Групповое меню</button>`
        : "";

    const dmBackButton = isPersonalMenuActive() && dmActiveSquadId != null
        ? `<button class="ghost-button dm-squad-back" type="button" data-action="dm-squad-back">← Мои отряды</button>`
        : "";

    mainMenuGrid.innerHTML = groupMenuBack + dmBackButton + items.map((item) => `
        <div class="menu-item-wrap">
            <button
                class="menu-button"
                type="button"
                data-view="${item.view || ""}"
                data-action="${item.action || ""}"
                ${item.disabled ? "disabled" : ""}
            >${escapeHtml(item.label)}</button>
            ${item.hint
                ? `<p class="menu-button-hint">${escapeHtml(item.hint)}</p>`
                : item.id === "create-squad"
                    ? '<p class="menu-button-hint menu-button-hint--spacer" aria-hidden="true"></p>'
                    : ""}
        </div>
    `).join("");

    mainMenuGrid.querySelector("[data-action='group-menu-back']")?.addEventListener("click", () => {
        personalMenuFromGroup = false;
        dmActiveSquadId = null;
        renderShell();
    });

    mainMenuGrid.querySelector("[data-action='dm-squad-back']")?.addEventListener("click", () => {
        dmActiveSquadId = null;
        selectedGameId = null;
        renderShell();
    });

    mainMenuGrid.querySelectorAll(".menu-button").forEach((button) => {
        button.addEventListener("click", async () => {
            if (button.disabled) {
                return;
            }
            const action = button.dataset.action;
            if (action === "request-friend" || action === "request-join") {
                await submitSquadRequest(action === "request-friend" ? "friend" : "join");
                return;
            }
            if (action === "leave-friendship") {
                await leaveSquadFriendship();
                return;
            }
            const view = button.dataset.view;
            if (view) {
                showView(view);
            }
        });
    });

    mainMenu.classList.remove("hidden");
}

async function submitSquadRequest(requestType) {
    const squadId = contextSquadId();
    if (!squadId) {
        setStatus("Откройте приложение из чата отряда.", true);
        return;
    }
    try {
        await api(`/api/v1/squads/${squadId}/requests`, {
            method: "POST",
            body: JSON.stringify({ request_type: requestType }),
        });
        me = await api("/api/v1/me");
        appScenario = resolveAppScenario(me, launch);
        renderShell();
        setStatus("Заявка отправлена.");
    } catch (error) {
        showErrorToast(error);
    }
}

async function leaveSquadFriendship() {
    const squadId = contextSquadId();
    if (!squadId) {
        setStatus("Откройте приложение из чата отряда.", true);
        return;
    }
    const squad = getSquadById(squadId);
    const squadName = squad?.name || "отряд";
    const confirmed = await showConfirmDialog({
        message: `Покинуть отряд «${squadName}»? Вы перестанете быть другом отряда.`,
        confirmLabel: "Покинуть",
        cancelLabel: "Отмена",
        danger: true,
    });
    if (!confirmed) {
        return;
    }
    try {
        await api(`/api/v1/squads/${squadId}/friendship`, { method: "DELETE" });
        me = await api("/api/v1/me");
        appScenario = resolveAppScenario(me, launch);
        renderShell();
        setStatus("Вы покинули отряд.");
    } catch (error) {
        showErrorToast(error);
    }
}

function renderShell() {
    appScenario = resolveAppScenario(me, launch);
    if (currentView !== "home") {
        return;
    }
    renderContextBanner();
    renderIdentityBar();
    renderProfileControls();
    renderMainMenu();
}

function syncViewChrome() {
    if (currentView === "home") {
        viewHeader.classList.add("hidden");
        registrationCard.classList.add("hidden");
        content.classList.add("hidden");
        gameSelectorEl.classList.add("hidden");
        return;
    }

    mainMenu.classList.add("hidden");
    viewHeader.classList.remove("hidden");
    profileControls.classList.add("hidden");
    identityBar?.classList.add("hidden");
    contextBanner.classList.add("hidden");

    if (currentView === "add-squad") {
        registrationCard.classList.remove("hidden");
        content.classList.add("hidden");
        gameSelectorEl.classList.add("hidden");
        return;
    }

    registrationCard.classList.add("hidden");
    content.classList.remove("hidden");
    attendanceTab.classList.toggle("hidden", currentView !== "attendance");
    summaryTab.classList.toggle("hidden", currentView !== "summary");
    adminTab.classList.toggle("hidden", currentView !== "admin");
    membersTab.classList.toggle("hidden", currentView !== "members");
    createSquadTab?.classList.toggle("hidden", currentView !== "create-squad");
    gameSelectorEl.classList.toggle("hidden", currentView !== "attendance" && currentView !== "summary");
}

function showHome() {
    currentView = "home";
    dockMode = false;
    dmActiveSquadId = null;
    personalMenuFromGroup = false;
    syncViewChrome();
    renderShell();
}

function showView(view) {
    currentView = view;
    syncViewChrome();

    if (view === "add-squad") {
        viewTitle.textContent = "Добавить отряд";
        renderRegistration();
        return;
    }

    const titles = {
        attendance: "Расписание",
        summary: "Посещаемость",
        members: "Участники",
        admin: "Управление отрядом",
        "create-squad": "Создать отряд",
    };
    viewTitle.textContent = titles[view] || "Отряд";

    if (view === "attendance") {
        renderGameSelector();
        void renderAttendances();
    } else if (view === "summary") {
        renderGameSelector();
        renderSummary();
    } else if (view === "members") {
        void renderMembers();
    } else if (view === "admin") {
        renderAdmin();
    } else if (view === "create-squad") {
        if (!isSoloGroupAdminNoSquad()) {
            showHome();
            return;
        }
        renderCreateSquad();
    }
}

function squadQuery(extra = {}) {
    const params = new URLSearchParams();
    const squadId = dockMode ? ownSquadId() : (contextSquadId() ?? me?.primary_squad_id);
    if (squadId) {
        params.set("squad_id", String(squadId));
    }
    if (selectedGameId != null) {
        params.set("game_id", String(selectedGameId));
    }
    Object.entries(extra).forEach(([key, value]) => {
        if (value != null) {
            params.set(key, String(value));
        }
    });
    const query = params.toString();
    return query ? `?${query}` : "";
}

async function api(path, options = {}) {
    if (typeof window.__previewApi === "function") {
        return window.__previewApi(path, options);
    }

    setLoading(true);
    try {
        const initData = getInitData();
        const headers = {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...(options.headers || {}),
        };

        if (initData) {
            headers.Authorization = `tma ${initData}`;
            headers["X-Telegram-Init-Data"] = initData;
        }

        const debugToken = getStoredDebugToken();
        if (debugToken) {
            headers["X-Debug-Token"] = debugToken;
        }

        const response = await fetch(path, {
            ...options,
            headers,
        });

        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            const { code, message } = parseApiError(payload.detail, response.status);
            throw new ApiError(code, message, response.status);
        }

        if (response.status === 204) {
            return null;
        }
        return response.json();
    } finally {
        setLoading(false);
    }
}

function getFieldWrapper(name) {
    return registrationCard?.querySelector(`[data-field="${name}"]`);
}

function setFieldError(name, message) {
    const field = getFieldWrapper(name);
    if (!field) {
        return;
    }
    const errorEl = field.querySelector(".field-error");
    field.classList.add("field-invalid");
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.classList.remove("hidden");
    }
}

function clearFieldError(name) {
    const field = getFieldWrapper(name);
    if (!field) {
        return;
    }
    const errorEl = field.querySelector(".field-error");
    field.classList.remove("field-invalid");
    if (errorEl) {
        errorEl.textContent = "";
        errorEl.classList.add("hidden");
    }
}

function clearRegistrationFieldErrors() {
    clearFieldError("player-name");
    clearFieldError("squad");
}

function joinedSquadIds() {
    return new Set(squadMemberships().map((membership) => membership.squad_id));
}

function getRegistrationErrors() {
    const errors = {};
    const name = playerNameInput.value.trim();
    const addingSquad = isRegistered();
    const squadId = Number(squadIdInput.value);
    const squadQueryText = squadSearch?.value.trim() || "";

    if (!name) {
        errors["player-name"] = "Введите игровой ник.";
    }

    if (addingSquad) {
        if (squadQueryText && !squadId) {
            errors.squad = "Выберите отряд из списка или очистите поле.";
        } else if (squadId && joinedSquadIds().has(squadId)) {
            errors.squad = "Вы уже состоите в этом отряде.";
        }
    }

    return errors;
}

function updateRegistrationFormState(showErrors = false) {
    const errors = getRegistrationErrors();
    const isValid = Object.keys(errors).length === 0;

    clearRegistrationFieldErrors();
    if (showErrors) {
        Object.entries(errors).forEach(([field, message]) => setFieldError(field, message));
    } else {
        Object.keys(errors).forEach((field) => {
            const wrapper = getFieldWrapper(field);
            wrapper?.classList.toggle("field-invalid", true);
        });
    }

    if (registerButton) {
        registerButton.disabled = !isValid;
    }

    if (squadClear) {
        const hasSquadValue = Boolean(squadSearch?.value.trim() || squadIdInput?.value);
        squadClear.classList.toggle("hidden", !hasSquadValue);
    }

    return isValid;
}

function clearSquadSelection() {
    if (squadSearch) {
        squadSearch.value = "";
    }
    if (squadIdInput) {
        squadIdInput.value = "";
    }
    closeSquadList();
    updateRegistrationFormState();
}

function availableSquadsForRegistration() {
    const joined = joinedSquadIds();
    return squads.filter((squad) => !joined.has(squad.id));
}

function filterSquads(query) {
    const normalized = query.trim().toLowerCase();
    const available = availableSquadsForRegistration();
    if (!normalized) {
        return available;
    }
    return available.filter((squad) => squad.name.toLowerCase().includes(normalized));
}

function renderSquadList(query = "") {
    if (!squadList) {
        return;
    }

    const filtered = filterSquads(query);
    squadListIndex = -1;

    if (!filtered.length) {
        squadList.innerHTML = '<li class="squad-empty">Отряд не найден</li>';
        squadList.classList.remove("hidden");
        return;
    }

    squadList.innerHTML = filtered
        .map((squad) => `
            <li role="option" data-squad-id="${squad.id}" aria-selected="${squad.id === Number(squadIdInput.value)}">
                ${escapeHtml(squad.name)}
            </li>
        `)
        .join("");
    squadList.classList.remove("hidden");
}

function selectSquad(squad) {
    if (!squadIdInput || !squadSearch || !squadList) {
        return;
    }

    squadIdInput.value = String(squad.id);
    squadSearch.value = squad.name;
    squadList.classList.add("hidden");
    squadListIndex = -1;
    updateRegistrationFormState();
}

function openSquadList(showAll = false) {
    renderSquadList(showAll ? "" : squadSearch.value);
}

function closeSquadList() {
    if (!squadList) {
        return;
    }

    squadList.classList.add("hidden");
    squadListIndex = -1;
}

function setupSquadPicker() {
    if (!squadSearch || !squadList || !squadIdInput || !squadPicker) {
        return;
    }

    squadSearch.addEventListener("focus", () => {
        squadSearch.select();
        openSquadList(true);
    });
    squadSearch.addEventListener("input", () => {
        squadIdInput.value = "";
        openSquadList();
        updateRegistrationFormState();
    });
    squadSearch.addEventListener("blur", () => {
        updateRegistrationFormState(true);
    });
    squadSearch.addEventListener("keydown", (event) => {
        const items = [...squadList.querySelectorAll("[data-squad-id]")];
        if (!items.length) {
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            squadListIndex = Math.min(squadListIndex + 1, items.length - 1);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            squadListIndex = Math.max(squadListIndex - 1, 0);
        } else if (event.key === "Enter") {
            event.preventDefault();
            const item = items[squadListIndex >= 0 ? squadListIndex : 0];
            if (item) {
                const squad = squads.find((entry) => entry.id === Number(item.dataset.squadId));
                if (squad) {
                    selectSquad(squad);
                }
            }
            return;
        } else if (event.key === "Escape") {
            closeSquadList();
            return;
        } else {
            return;
        }

        items.forEach((item, index) => item.classList.toggle("active", index === squadListIndex));
        items[squadListIndex]?.scrollIntoView({ block: "nearest" });
    });

    squadList.addEventListener("mousedown", (event) => {
        const item = event.target.closest("[data-squad-id]");
        if (!item) {
            return;
        }
        event.preventDefault();
        const squad = squads.find((entry) => entry.id === Number(item.dataset.squadId));
        if (squad) {
            selectSquad(squad);
        }
    });

    document.addEventListener("click", (event) => {
        if (!squadPicker.contains(event.target)) {
            closeSquadList();
        }
    });

    squadClear?.addEventListener("click", () => {
        clearSquadSelection();
    });

    playerNameInput?.addEventListener("input", () => updateRegistrationFormState());
    playerNameInput?.addEventListener("blur", () => updateRegistrationFormState(true));
}

async function renderRegistration() {
    const addingSquad = isRegistered();
    registrationCard.classList.remove("hidden");
    if (registrationTitle) {
        registrationTitle.textContent = addingSquad ? "Добавить отряд" : "Регистрация";
    }

    const squadField = registrationCard?.querySelector('[data-field="squad"]');
    const registrationHint = registrationCard?.querySelector(".registration-hint");
    squadField?.classList.toggle("hidden", !addingSquad);
    if (registrationHint) {
        registrationHint.textContent = addingSquad
            ? "Выберите отряд для вступления."
            : "После регистрации отряд можно добавить в меню.";
    }

    clearSquadSelection();
    if (playerNameInput) {
        playerNameInput.value = hasSoloMembership()
            ? (me.memberships.find((membership) => membership.squad_id == null)?.name || "")
            : "";
    }

    try {
        squads = await api("/api/v1/squads");
        playerNameInput.disabled = false;
        if (squadSearch) {
            squadSearch.disabled = false;
        }
        updateRegistrationFormState();
    } catch (error) {
        setFieldError("squad", error.message);
        updateRegistrationFormState(true);
    }
}

async function registerPlayer() {
    if (!updateRegistrationFormState(true)) {
        return;
    }

    const name = playerNameInput.value.trim();
    const squadId = isRegistered() ? (Number(squadIdInput.value) || null) : null;

    try {
        await api("/api/v1/player", {
            method: "POST",
            body: JSON.stringify({
                squad_id: squadId,
                name,
            }),
        });
        playerNameInput.value = "";
        clearSquadSelection();
        await load();
        if (isRegistered()) {
            showHome();
        }
    } catch (error) {
        if (squadId) {
            setFieldError("squad", error.message);
        } else {
            setFieldError("player-name", error.message);
        }
        updateRegistrationFormState(true);
    }
}

function formatEventSchedule(item) {
    const time = String(item.game_time || "").slice(0, 5);
    const recurrence = item.recurrence_type || "weekly";
    if (recurrence === "once" && item.recurrence_date) {
        const dateText = String(item.recurrence_date).slice(0, 10).split("-").reverse().join(".");
        return `${dateText} в ${time} по МСК`;
    }
    if (recurrence === "monthly" && item.day_of_month) {
        return `${item.day_of_month}-го числа в ${time} по МСК`;
    }
    return `${dayNames[item.game_day_of_week] || "День"} в ${time} по МСК`;
}

function parseIsoDate(iso) {
    const [year, month, day] = String(iso).slice(0, 10).split("-").map(Number);
    return new Date(year, month - 1, day);
}

function toIsoDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function getMonday(date = new Date()) {
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const weekday = d.getDay();
    const diff = weekday === 0 ? -6 : 1 - weekday;
    d.setDate(d.getDate() + diff);
    return d;
}

function addDays(date, days) {
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    d.setDate(d.getDate() + days);
    return d;
}

function currentScheduleWeekStart() {
    return toIsoDate(getMonday());
}

function activeScheduleWeekStart() {
    return scheduleWeekStart || currentScheduleWeekStart();
}

function isCurrentScheduleWeek(weekStartIso) {
    return weekStartIso === currentScheduleWeekStart();
}

function monthlyOccurrenceOnDate(year, month, dayOfMonth) {
    const lastDay = new Date(year, month, 0).getDate();
    return new Date(year, month - 1, Math.min(dayOfMonth, lastDay));
}

function weekEndDate(weekStart) {
    return addDays(weekStart, 6);
}

function monthlyOccurrenceInWeek(weekStart, dayOfMonth) {
    for (let offset = 0; offset <= 1; offset += 1) {
        const probe = addDays(weekStart, offset * 7);
        const occurrence = monthlyOccurrenceOnDate(
            probe.getFullYear(),
            probe.getMonth() + 1,
            dayOfMonth,
        );
        if (occurrence >= weekStart && occurrence <= weekEndDate(weekStart)) {
            return occurrence;
        }
    }
    return null;
}

function presetOccurrenceInWeek(preset, weekStartIso) {
    const weekStart = parseIsoDate(weekStartIso);
    const recurrence = preset.recurrence_type || "weekly";

    if (recurrence === "weekly") {
        const weekday = preset.game_day_of_week;
        if (weekday == null) {
            return null;
        }
        return addDays(weekStart, Number(weekday));
    }

    if (recurrence === "monthly") {
        const dayOfMonth = preset.day_of_month;
        if (!dayOfMonth) {
            return null;
        }
        return monthlyOccurrenceInWeek(weekStart, Number(dayOfMonth));
    }

    if (!preset.recurrence_date) {
        return null;
    }
    const recurrenceDate = parseIsoDate(String(preset.recurrence_date).slice(0, 10));
    if (recurrenceDate >= weekStart && recurrenceDate <= weekEndDate(weekStart)) {
        return recurrenceDate;
    }
    return null;
}

function formatWeekRangeLabel(weekStartIso) {
    const start = parseIsoDate(weekStartIso);
    const end = weekEndDate(start);
    const startMonth = monthNamesGenitive[start.getMonth()];
    const endMonth = monthNamesGenitive[end.getMonth()];

    if (start.getMonth() === end.getMonth()) {
        return `${start.getDate()}–${end.getDate()} ${startMonth}`;
    }
    return `${start.getDate()} ${startMonth} – ${end.getDate()} ${endMonth}`;
}

function formatMonthLabel(weekStartIso) {
    const midWeek = addDays(parseIsoDate(weekStartIso), 3);
    return `${monthNamesNominative[midWeek.getMonth()]} ${midWeek.getFullYear()}`;
}

function shiftScheduleWeek(deltaWeeks) {
    const next = addDays(parseIsoDate(activeScheduleWeekStart()), deltaWeeks * 7);
    scheduleWeekStart = toIsoDate(getMonday(next));
}

function shiftScheduleMonth(deltaMonths) {
    const midWeek = addDays(parseIsoDate(activeScheduleWeekStart()), 3);
    const firstOfMonth = new Date(midWeek.getFullYear(), midWeek.getMonth() + deltaMonths, 1);
    scheduleWeekStart = toIsoDate(getMonday(firstOfMonth));
}

function scheduleGridHtml(weekStartIso, attendances) {
    const weekStart = parseIsoDate(weekStartIso);
    const todayIso = toIsoDate(new Date());
    const eventsByDay = Array.from({ length: 7 }, () => []);

    attendances.forEach((entry) => {
        const preset = entry.schedule_preset || entry;
        const occurrence = presetOccurrenceInWeek(preset, weekStartIso);
        if (!occurrence) {
            return;
        }
        const dayIndex = Math.round((occurrence - weekStart) / (24 * 60 * 60 * 1000));
        if (dayIndex < 0 || dayIndex > 6) {
            return;
        }
        eventsByDay[dayIndex].push({
            preset,
            time: String(preset.game_time || "").slice(0, 5),
        });
    });

    eventsByDay.forEach((events) => {
        events.sort((left, right) => left.time.localeCompare(right.time) || left.preset.id - right.preset.id);
    });

    const dayHeaders = Array.from({ length: 7 }, (_, index) => {
        const dayDate = addDays(weekStart, index);
        const dayIso = toIsoDate(dayDate);
        const isToday = dayIso === todayIso;
        return `
            <div class="schedule-day-header${isToday ? " schedule-day-header--today" : ""}">
                <span class="schedule-day-name">${dayNamesShort[index]}</span>
                <span class="schedule-day-date">${dayDate.getDate()}</span>
            </div>
        `;
    }).join("");

    const dayColumns = eventsByDay.map((events, index) => {
        const dayDate = addDays(weekStart, index);
        const dayIso = toIsoDate(dayDate);
        const isToday = dayIso === todayIso;
        const eventsHtml = events.length
            ? events.map(({ preset, time }) => {
                const gameTitle = preset.game?.title;
                const recurrence = preset.recurrence_type || "weekly";
                const recurrenceBadge = recurrence !== "weekly"
                    ? `<span class="schedule-event-badge">${escapeHtml(recurrenceLabels[recurrence] || recurrence)}</span>`
                    : "";
                return `
                    <div class="schedule-event">
                        <span class="schedule-event-time">${escapeHtml(time)}</span>
                        <span class="schedule-event-title">${escapeHtml(preset.title)}${recurrenceBadge}</span>
                        ${gameTitle ? `<span class="schedule-event-game">${escapeHtml(gameTitle)}</span>` : ""}
                    </div>
                `;
            }).join("")
            : `<div class="schedule-day-empty" aria-hidden="true"></div>`;

        return `
            <div class="schedule-day-column${isToday ? " schedule-day-column--today" : ""}">
                ${eventsHtml}
            </div>
        `;
    }).join("");

    return `
        <div class="schedule-panel card">
            <div class="schedule-toolbar">
                <div class="schedule-nav-group">
                    <button class="schedule-nav-btn" type="button" data-schedule-action="month-prev" aria-label="Предыдущий месяц">‹</button>
                    <span class="schedule-nav-label schedule-nav-label--month">${escapeHtml(formatMonthLabel(weekStartIso))}</span>
                    <button class="schedule-nav-btn" type="button" data-schedule-action="month-next" aria-label="Следующий месяц">›</button>
                </div>
                <div class="schedule-nav-group">
                    <button class="schedule-nav-btn" type="button" data-schedule-action="week-prev" aria-label="Предыдущая неделя">‹</button>
                    <span class="schedule-nav-label schedule-nav-label--week">${escapeHtml(formatWeekRangeLabel(weekStartIso))}</span>
                    <button class="schedule-nav-btn" type="button" data-schedule-action="week-next" aria-label="Следующая неделя">›</button>
                    ${isCurrentScheduleWeek(weekStartIso)
                        ? ""
                        : '<button class="schedule-nav-btn schedule-nav-btn--today" type="button" data-schedule-action="week-today">Сегодня</button>'}
                </div>
            </div>
            <div class="schedule-grid">
                <div class="schedule-grid-header">
                    ${dayHeaders}
                </div>
                <div class="schedule-grid-body">
                    ${dayColumns}
                </div>
            </div>
        </div>
    `;
}

function bindScheduleNavigation() {
    attendanceTab.querySelectorAll("[data-schedule-action]").forEach((button) => {
        button.addEventListener("click", async () => {
            const action = button.dataset.scheduleAction;
            if (action === "week-prev") {
                shiftScheduleWeek(-1);
            } else if (action === "week-next") {
                shiftScheduleWeek(1);
            } else if (action === "month-prev") {
                shiftScheduleMonth(-1);
            } else if (action === "month-next") {
                shiftScheduleMonth(1);
            } else if (action === "week-today") {
                scheduleWeekStart = currentScheduleWeekStart();
            }
            await renderAttendances();
        });
    });
}

function renderAttendanceCards(attendances, { readOnly }) {
    return attendances.map(({ schedule_preset, attend_status, weekly_attend_status, comment }) => {
        const alwaysAttend = schedule_preset.will_attend_default === true;
        const autoApplied = alwaysAttend
            && weekly_attend_status == null
            && attend_status === "will_attend";
        const weeklyControlsHtml = alwaysAttend
            ? `
                <div class="segmented segmented--always-attend">
                    ${attendanceButton(schedule_preset.id, "will_attend", true, "Приду", true)}
                    ${attendanceButton(schedule_preset.id, "null", false, "Сбросить")}
                </div>
            `
            : `
                <div class="segmented">
                    ${attendanceButton(schedule_preset.id, "will_attend", attend_status === "will_attend", "Приду")}
                    ${attendanceButton(schedule_preset.id, "doubts", attend_status === "doubts", "Сомневаюсь")}
                    ${attendanceButton(schedule_preset.id, "will_not_attend", attend_status === "will_not_attend", "Не приду")}
                    ${attendanceButton(schedule_preset.id, "null", weekly_attend_status == null, "Сбросить")}
                </div>
            `;
        return `
            <article class="card event-card ${readOnly ? "event-card--readonly" : ""}" data-preset-id="${schedule_preset.id}">
                ${eventHeader(schedule_preset)}
                ${readOnly ? "" : `
                <label class="always-attend-toggle always-attend-toggle--card">
                    <input
                        type="checkbox"
                        data-always-attend-for="${schedule_preset.id}"
                        ${alwaysAttend ? "checked" : ""}
                    >
                    <span>Всегда буду приходить</span>
                </label>`}
                ${autoApplied ? '<p class="auto-attend-hint">На эту неделю: приду автоматически</p>' : ""}
                ${readOnly || alwaysAttend ? "" : `
                <div class="comment-field">
                    <textarea
                        data-comment-for="${schedule_preset.id}"
                        data-current-status="${attend_status ?? ""}"
                        maxlength="100"
                        placeholder="Комментарий, если нужен"
                    >${escapeHtml(comment || "")}</textarea>
                    <button
                        class="comment-apply-btn"
                        type="button"
                        data-comment-apply-for="${schedule_preset.id}"
                        aria-label="Применить комментарий"
                        title="Применить"
                    >✓</button>
                </div>`}
                ${readOnly ? `<p class="readonly-hint">Просмотр расписания. Заявки доступны друзьям отряда и участникам.</p>` : weeklyControlsHtml}
            </article>
        `;
    }).join("");
}

function eventHeader(item) {
    const gameTitle = item.game?.title;
    const gameLine = gameTitle
        ? `<p class="game-title">${escapeHtml(gameTitle)}</p>`
        : "";
    const recurrence = item.recurrence_type || "weekly";
    const recurrenceBadge = recurrence !== "weekly"
        ? `<span class="admin-badge">${recurrenceLabels[recurrence] || recurrence}</span>`
        : "";
    return `
        <div>
            <h3>${escapeHtml(item.title)}${recurrenceBadge}</h3>
            ${gameLine}
            <p>${formatEventSchedule(item)}</p>
        </div>
    `;
}

function filterByGame(items) {
    if (selectedGameId == null) {
        return items;
    }
    return items.filter((item) => {
        const preset = item.schedule_preset || item;
        return preset.game?.id === selectedGameId;
    });
}

async function renderAttendances() {
    const isSoloOutsider = shouldUseSoloMenuInContext()
        && (me?.squad_relation === "outsider" || me?.squad_relation === "pending");
    const readOnly = isSoloOutsider;
    const weekStartIso = activeScheduleWeekStart();
    const isCurrentWeek = isCurrentScheduleWeek(weekStartIso);

    let attendances = await api(`/api/v1/attendances${squadQuery({ week_start: weekStartIso })}`);
    attendances = filterByGame(attendances);

    const gridHtml = scheduleGridHtml(weekStartIso, attendances);

    if (!attendances.length) {
        attendanceTab.innerHTML = `
            ${gridHtml}
            <div class="empty schedule-empty-hint">Нет событий на этой неделе.</div>
        `;
        bindScheduleNavigation();
        return;
    }

    const attendanceCardsHtml = isCurrentWeek
        ? renderAttendanceCards(attendances, { readOnly })
        : "";

    attendanceTab.innerHTML = `
        ${gridHtml}
        ${attendanceCardsHtml ? `
            <section class="schedule-attendance-section">
                <h3 class="schedule-attendance-title">Заявки на эту неделю</h3>
                ${attendanceCardsHtml}
            </section>
        ` : ""}
    `;

    bindScheduleNavigation();

    if (readOnly || !isCurrentWeek) {
        return;
    }

    attendanceTab.querySelectorAll("[data-always-attend-for]").forEach((checkbox) => {
        checkbox.addEventListener("change", async () => {
            const presetId = checkbox.dataset.alwaysAttendFor;
            try {
                if (checkbox.checked) {
                    await api(`/api/v1/schedules/${presetId}${squadQuery()}`, {
                        method: "PUT",
                        body: JSON.stringify({ will_attend_default: true }),
                    });
                    await api(`/api/v1/attendances/${presetId}${squadQuery()}`, {
                        method: "PUT",
                        body: JSON.stringify({ attend_status: null, comment: "" }),
                    });
                } else {
                    await api(`/api/v1/schedules/${presetId}${squadQuery()}`, {
                        method: "PUT",
                        body: JSON.stringify({ will_attend_default: null }),
                    });
                }
                await renderAttendances();
            } catch (error) {
                checkbox.checked = !checkbox.checked;
                showErrorToast(error);
            }
        });
    });

    attendanceTab.querySelectorAll("[data-comment-apply-for]").forEach((button) => {
        button.addEventListener("click", async () => {
            const presetId = button.dataset.commentApplyFor;
            const textarea = attendanceTab.querySelector(`[data-comment-for="${presetId}"]`);
            const comment = textarea?.value || "";
            const rawStatus = textarea?.dataset.currentStatus ?? "";
            const attendStatus = rawStatus === "" ? null : rawStatus;

            if (attendStatus == null) {
                showErrorToast(null, "Сначала выберите статус посещения");
                return;
            }

            button.disabled = true;
            try {
                await api(`/api/v1/attendances/${presetId}${squadQuery()}`, {
                    method: "PUT",
                    body: JSON.stringify({
                        attend_status: attendStatus,
                        comment,
                    }),
                });
                await renderAttendances();
            } catch (error) {
                showErrorToast(error);
            } finally {
                button.disabled = false;
            }
        });
    });

    attendanceTab.querySelectorAll("[data-attendance-value]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (button.disabled) {
                return;
            }
            const presetId = button.dataset.presetId;
            const value = button.dataset.attendanceValue;
            const alwaysAttendCheckbox = attendanceTab.querySelector(`[data-always-attend-for="${presetId}"]`);
            const comment = attendanceTab.querySelector(`[data-comment-for="${presetId}"]`)?.value || "";
            try {
                if (value === "null" && alwaysAttendCheckbox?.checked) {
                    await api(`/api/v1/schedules/${presetId}${squadQuery()}`, {
                        method: "PUT",
                        body: JSON.stringify({ will_attend_default: null }),
                    });
                    await api(`/api/v1/attendances/${presetId}${squadQuery()}`, {
                        method: "PUT",
                        body: JSON.stringify({ attend_status: null, comment }),
                    });
                } else {
                    await api(`/api/v1/attendances/${presetId}${squadQuery()}`, {
                        method: "PUT",
                        body: JSON.stringify({
                            attend_status: value === "null" ? null : value,
                            comment,
                        }),
                    });
                }
                await renderAttendances();
            } catch (error) {
                showErrorToast(error);
            }
        });
    });
}

function attendanceButton(presetId, value, active, label, disabled = false) {
    return `
        <button
            class="${active ? "active" : ""}"
            data-preset-id="${presetId}"
            data-attendance-value="${value}"
            type="button"
            ${disabled ? "disabled" : ""}
        >${label}</button>
    `;
}

async function renderSummary() {
    let summary = await api(`/api/v1/attendance-summary${squadQuery()}`);
    summary = filterByGame(summary);

    if (!summary.length) {
        summaryTab.innerHTML = emptyHtml();
        return;
    }

    summaryTab.innerHTML = summary.map(({ schedule_preset, players }) => `
        <article class="card event-card">
            ${eventHeader(schedule_preset)}
            ${["will_attend", "doubts", "will_not_attend"].map((status) => summaryGroup(status, players)).join("")}
        </article>
    `).join("");
}

function summaryGroup(status, players) {
    const filtered = players.filter((player) => player.attend_status === status);
    if (!filtered.length) {
        return "";
    }
    return `
        <div class="summary-group">
            <strong>${statusLabels[status]} (${filtered.length})</strong>
            <ul>
                ${filtered.map((player) => `
                    <li>${escapeHtml(player.player_name)}${player.comment ? ` — ${escapeHtml(player.comment)}` : ""}</li>
                `).join("")}
            </ul>
        </div>
    `;
}

async function renderCreateSquad() {
    createSquadForm?.classList.remove("hidden");
    createSquadSuccess?.classList.add("hidden");

    const nameInput = document.querySelector("#create-squad-name-input");
    const tagsInput = document.querySelector("#create-squad-tags-input");
    if (nameInput) {
        nameInput.value = "";
    }
    if (tagsInput) {
        tagsInput.value = "";
    }
}

function showCreateSquadSuccess() {
    createSquadForm?.classList.add("hidden");
    createSquadSuccess?.classList.remove("hidden");
    hideStatus();
}

async function createSquad() {
    if (!isSoloGroupAdminNoSquad()) {
        setStatus("access_denied", true);
        return;
    }

    const nameInput = document.querySelector("#create-squad-name-input");
    const tagsInput = document.querySelector("#create-squad-tags-input");
    const name = nameInput?.value.trim() || "";
    const tags = tagsInput?.value.trim() || "";

    if (!name) {
        setStatus("Укажите название отряда.", true);
        return;
    }
    if (!tags) {
        setStatus("Укажите клан-теги.", true);
        return;
    }

    try {
        await api("/api/v1/squads/create-from-chat", {
            method: "POST",
            body: JSON.stringify({ name, tags }),
        });
        me = await api("/api/v1/me");
        squads = await api("/api/v1/squads");
        launch = resolveLaunchContext(me);
        appScenario = resolveAppScenario(me, launch);
        showCreateSquadSuccess();
    } catch (error) {
        showErrorToast(error);
    }
}

async function renderMembers() {
    syncViewChrome();

    const squadId = dockMode ? ownSquadId() : (contextSquadId() ?? me?.primary_squad_id);
    if (!squadId) {
        membersTab.innerHTML = `<div class="empty">Отряд не выбран.</div>`;
        return;
    }

    membersTab.innerHTML = `<div class="empty">Загрузка…</div>`;

    try {
        const members = await api(`/api/v1/squads/${squadId}/members`);
        if (!members.length) {
            membersTab.innerHTML = `<div class="empty">В отряде пока нет участников.</div>`;
            return;
        }

        membersTab.innerHTML = `
            <article class="card">
                <ul class="membership-list" role="list">
                    ${members.map((member) => `
                        <li class="membership-item">
                            <span>${formatSquadMemberLabel(member)}</span>
                        </li>
                    `).join("")}
                </ul>
            </article>
        `;
    } catch (error) {
        membersTab.innerHTML = `<div class="empty">Не удалось загрузить список участников.</div>`;
        showErrorToast(error);
    }
}

async function renderAdmin() {
    syncViewChrome();

    const squadId = dockMode ? ownSquadId() : (contextSquadId() ?? resolveAdminSquadId() ?? me?.primary_squad_id);
    const isAdmin = dmActiveSquadId != null
        ? isEffectiveSquadAdmin(dmActiveSquadId)
        : isEffectiveSquadAdmin(squadId);

    if (!squadId || !isAdmin) {
        adminTab.innerHTML = `<div class="empty">Недостаточно прав.</div>`;
        return;
    }

    let members = [];
    let friends = [];
    let requests = [];
    let blocked = [];
    let allGames = games;
    let schedulePresets = [];

    try {
        [members, friends, requests, blocked, allGames, schedulePresets] = await Promise.all([
            api(`/api/v1/squads/${squadId}/members`),
            api(`/api/v1/squads/${squadId}/friends`),
            api(`/api/v1/squads/${squadId}/requests`),
            api(`/api/v1/squads/${squadId}/blocked`),
            games.length ? Promise.resolve(games) : api("/api/v1/games"),
            api(`/api/v1/squads/${squadId}/schedule-presets`).catch(() => []),
        ]);
    } catch (error) {
        adminTab.innerHTML = `<div class="empty">Не удалось загрузить панель управления.</div>`;
        showErrorToast(error);
        return;
    }
    games = allGames;

    const squad = getSquadById(squadId) || { games: [], main_game_ids: [] };
    const squadGameIds = (squad.games || []).map((game) => game.id);
    let draftGameIds = [...squadGameIds];
    let draftMainGameIds = (squad.main_game_ids || []).filter((gameId) => squadGameIds.includes(gameId));

    function gamesCardHtml() {
        const squadGames = getSquadById(squadId)?.games || [];
        const gamesById = new Map(squadGames.map((game) => [game.id, game]));
        const rows = draftGameIds.map((gameId) => {
            const game = gamesById.get(gameId);
            if (!game) {
                return "";
            }
            const isMain = draftMainGameIds.includes(gameId);
            return `
                <div class="admin-game-row ${isMain ? "is-main" : ""}" draggable="true" data-game-id="${gameId}">
                    <span class="admin-game-drag" title="Перетащить" aria-hidden="true">::</span>
                    <div class="admin-game-main">
                        <span class="admin-game-title">${escapeHtml(game.title)}</span>
                        ${isMain ? '<span class="admin-game-main-badge">главная</span>' : ""}
                    </div>
                    <div class="admin-game-actions">
                        <button
                            type="button"
                            class="admin-icon-button ${isMain ? "active" : ""}"
                            data-toggle-main="${gameId}"
                            title="Сделать главной"
                            aria-label="Сделать главной"
                        >★</button>
                        <button
                            type="button"
                            class="admin-icon-button admin-icon-button--danger"
                            data-remove-game="${gameId}"
                            title="Удалить игру из отряда"
                            aria-label="Удалить игру из отряда"
                        >✕</button>
                    </div>
                </div>
            `;
        }).join("");
        return `
            <article class="card">
                <h3>Игры отряда</h3>
                <form class="admin-game-add" id="admin-game-add-form">
                    <input
                        id="admin-game-input"
                        type="text"
                        maxlength="50"
                        placeholder="Введите название игры"
                        autocomplete="off"
                    >
                    <button class="admin-submit-button" type="submit" title="Добавить игру" aria-label="Добавить игру">→</button>
                </form>
                <div class="admin-games-panel">
                    <div class="admin-games-list">
                        ${rows || '<p class="empty-inline">Добавьте первую игру.</p>'}
                    </div>
                </div>
            </article>
        `;
    }

    function scheduleCardHtml() {
        const squadGames = getSquadById(squadId)?.games || [];
        const gameOptions = squadGames.map((game) => `
            <option value="${game.id}">${escapeHtml(game.title)}</option>
        `).join("");
        const rows = (schedulePresets || []).map((preset) => `
            <div class="admin-schedule-row" data-preset-id="${preset.id}">
                <div class="admin-schedule-info">
                    <strong>${escapeHtml(preset.title)}</strong>
                    <span class="admin-badge">${recurrenceLabels[preset.recurrence_type] || preset.recurrence_type}</span>
                    <p>${formatEventSchedule(preset)}</p>
                    ${preset.game?.title ? `<p class="game-title">${escapeHtml(preset.game.title)}</p>` : ""}
                </div>
                <button
                    type="button"
                    class="admin-icon-button admin-icon-button--danger"
                    data-delete-preset="${preset.id}"
                    title="Удалить событие"
                    aria-label="Удалить событие"
                >✕</button>
            </div>
        `).join("");
        const weekdayOptions = dayNames.map((label, index) => `
            <option value="${index}">${label}</option>
        `).join("");
        const monthDayOptions = Array.from({ length: 31 }, (_, index) => {
            const day = index + 1;
            return `<option value="${day}">${day}</option>`;
        }).join("");
        return `
            <article class="card">
                <h3>Расписание</h3>
                <form class="admin-schedule-form" id="admin-schedule-form">
                    <div class="admin-schedule-form-row admin-schedule-form-row--title">
                        <input
                            id="admin-schedule-title"
                            class="admin-input"
                            type="text"
                            maxlength="50"
                            placeholder="Название события"
                            autocomplete="off"
                            required
                        >
                    </div>
                    <div class="admin-schedule-form-row admin-schedule-form-row--timing">
                        <div class="admin-select-wrap">
                            <select id="admin-schedule-recurrence" class="admin-select" required>
                                <option value="weekly">Еженедельно</option>
                                <option value="monthly">Ежемесячно</option>
                                <option value="once">Единоразово</option>
                            </select>
                        </div>
                        <div class="admin-schedule-timing-slot">
                            <div class="admin-select-wrap schedule-field schedule-field--weekly">
                                <select id="admin-schedule-weekday" class="admin-select">
                                    ${weekdayOptions}
                                </select>
                            </div>
                            <div class="admin-select-wrap schedule-field schedule-field--monthly hidden">
                                <select id="admin-schedule-monthday" class="admin-select">
                                    ${monthDayOptions}
                                </select>
                            </div>
                            <input
                                id="admin-schedule-date"
                                type="date"
                                class="admin-input schedule-field schedule-field--once hidden"
                            >
                        </div>
                        <input id="admin-schedule-time" class="admin-input" type="time" value="20:00" required>
                    </div>
                    <div class="admin-schedule-form-row admin-schedule-form-row--game">
                        <div class="admin-select-wrap admin-schedule-game-wrap">
                            <select id="admin-schedule-game" class="admin-select" required ${squadGames.length ? "" : "disabled"}>
                                ${gameOptions || '<option value="">Сначала добавьте игру</option>'}
                            </select>
                        </div>
                        <button class="admin-submit-button" type="submit" title="Добавить событие" aria-label="Добавить событие" ${squadGames.length ? "" : "disabled"}>→</button>
                    </div>
                </form>
                <div class="admin-schedule-list">
                    ${rows || '<p class="empty-inline">Добавьте первое событие.</p>'}
                </div>
            </article>
        `;
    }

    adminTab.innerHTML = `
        ${gamesCardHtml()}
        ${scheduleCardHtml()}
        <article class="card">
            <h3>Заявки</h3>
            ${requests.length ? requests.map((request) => `
                <div class="admin-row">
                    <span>${escapeHtml(request.player_name || "Игрок")} — ${request.request_type === "join" ? "вступление" : "друг"}</span>
                    <div class="admin-actions">
                        <button type="button" data-action="accept" data-request-id="${request.id}">Принять</button>
                        <button type="button" data-action="reject" data-request-id="${request.id}">Отклонить</button>
                        <button type="button" data-action="block" data-request-id="${request.id}">Заблокировать</button>
                    </div>
                </div>
            `).join("") : `<p class="empty-inline">Нет заявок.</p>`}
        </article>
        <article class="card">
            <h3>Заблокированные</h3>
            ${blocked.length ? blocked.map((user) => `
                <div class="admin-row">
                    <span>${escapeHtml(user.player_name)}</span>
                    <button type="button" data-unblock-id="${user.telegram_id}">Разблокировать</button>
                </div>
            `).join("") : `<p class="empty-inline">Никто не заблокирован.</p>`}
        </article>
        <article class="card">
            <h3>Участники</h3>
            ${members.map((member) => `
                <div class="admin-row">
                    <span>${formatSquadMemberLabel(member)}</span>
                    ${member.is_telegram_admin ? "" : `<button type="button" data-remove-member="${member.telegram_id}">Удалить</button>`}
                </div>
            `).join("")}
        </article>
        <article class="card">
            <h3>Друзья отряда</h3>
            ${friends.length ? friends.map((friend) => `
                <div class="admin-row">
                    <span>${escapeHtml(friend.name)}</span>
                    <button type="button" data-remove-friend="${friend.id}">Удалить из друзей</button>
                </div>
            `).join("") : `<p class="empty-inline">Нет друзей.</p>`}
        </article>
    `;

    async function refreshSquadGamesView() {
        squads = await api("/api/v1/squads");
        syncViewChrome();
        if (currentView === "admin") {
            await renderAdmin();
        }
    }

    async function persistDraftGames() {
        try {
            await api(`/api/v1/squads/${squadId}/games`, {
                method: "PUT",
                body: JSON.stringify({
                    game_ids: draftGameIds,
                    main_game_ids: draftMainGameIds,
                }),
            });
            await refreshSquadGamesView();
        } catch (error) {
            showErrorToast(error);
        }
    }

    adminTab.querySelector("#admin-game-add-form")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const input = adminTab.querySelector("#admin-game-input");
        const title = input?.value.trim() || "";
        if (!title) {
            return;
        }
        try {
            await api(`/api/v1/squads/${squadId}/games`, {
                method: "POST",
                body: JSON.stringify({ title }),
            });
            input.value = "";
            await refreshSquadGamesView();
            setStatus("Игра добавлена.");
        } catch (error) {
            showErrorToast(error);
        }
    });

    const recurrenceSelect = adminTab.querySelector("#admin-schedule-recurrence");
    const scheduleFields = {
        weekly: adminTab.querySelector("#admin-schedule-weekday"),
        monthly: adminTab.querySelector("#admin-schedule-monthday"),
        once: adminTab.querySelector("#admin-schedule-date"),
    };

    function syncScheduleFields() {
        const recurrence = recurrenceSelect?.value || "weekly";
        const scheduleWraps = {
            weekly: adminTab.querySelector(".schedule-field--weekly"),
            monthly: adminTab.querySelector(".schedule-field--monthly"),
            once: adminTab.querySelector(".schedule-field--once"),
        };
        Object.entries(scheduleWraps).forEach(([type, wrap]) => {
            wrap?.classList.toggle("hidden", type !== recurrence);
        });
        if (scheduleFields.weekly) {
            scheduleFields.weekly.required = recurrence === "weekly";
        }
        if (scheduleFields.monthly) {
            scheduleFields.monthly.required = recurrence === "monthly";
        }
        if (scheduleFields.once) {
            scheduleFields.once.required = recurrence === "once";
        }
    }

    recurrenceSelect?.addEventListener("change", syncScheduleFields);
    syncScheduleFields();

    adminTab.querySelector("#admin-schedule-form")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const title = adminTab.querySelector("#admin-schedule-title")?.value.trim() || "";
        const recurrenceType = recurrenceSelect?.value || "weekly";
        const gameTime = adminTab.querySelector("#admin-schedule-time")?.value || "";
        const gameIdRaw = adminTab.querySelector("#admin-schedule-game")?.value || "";
        if (!title || !gameTime || !gameIdRaw) {
            if (!gameIdRaw) {
                setStatus("Выберите игру для события.", true);
            }
            return;
        }
        const payload = {
            title,
            recurrence_type: recurrenceType,
            game_time: gameTime,
            game_id: Number(gameIdRaw),
        };
        if (recurrenceType === "weekly") {
            payload.game_day_of_week = Number(scheduleFields.weekly?.value || 0);
        } else if (recurrenceType === "monthly") {
            payload.day_of_month = Number(scheduleFields.monthly?.value || 1);
        } else {
            const recurrenceDate = scheduleFields.once?.value || "";
            if (!recurrenceDate) {
                setStatus("Укажите дату для единоразового события.", true);
                return;
            }
            payload.recurrence_date = recurrenceDate;
        }
        try {
            await api(`/api/v1/squads/${squadId}/schedule-presets`, {
                method: "POST",
                body: JSON.stringify(payload),
            });
            await renderAdmin();
            setStatus("Событие добавлено.");
        } catch (error) {
            showErrorToast(error);
        }
    });

    adminTab.querySelectorAll("[data-delete-preset]").forEach((button) => {
        button.addEventListener("click", async () => {
            const presetId = button.dataset.deletePreset;
            if (!window.confirm("Удалить событие из расписания?")) {
                return;
            }
            try {
                await api(`/api/v1/squads/${squadId}/schedule-presets/${presetId}`, { method: "DELETE" });
                await renderAdmin();
                setStatus("Событие удалено.");
            } catch (error) {
                showErrorToast(error);
            }
        });
    });

    adminTab.querySelectorAll("[data-toggle-main]").forEach((button) => {
        button.addEventListener("click", async () => {
            const gameId = Number(button.dataset.toggleMain);
            if (draftMainGameIds.includes(gameId)) {
                draftMainGameIds = draftMainGameIds.filter((id) => id !== gameId);
            } else {
                draftMainGameIds = [...draftMainGameIds, gameId];
            }
            await persistDraftGames();
            setStatus("Главные игры обновлены.");
        });
    });

    adminTab.querySelectorAll("[data-remove-game]").forEach((button) => {
        button.addEventListener("click", async () => {
            const gameId = Number(button.dataset.removeGame);
            try {
                await api(`/api/v1/squads/${squadId}/games/${gameId}`, { method: "DELETE" });
                await refreshSquadGamesView();
                setStatus("Игра отвязана от отряда.");
            } catch (error) {
                showErrorToast(error);
            }
        });
    });

    let draggedGameId = null;
    adminTab.querySelectorAll(".admin-game-row").forEach((row) => {
        row.addEventListener("dragstart", (event) => {
            draggedGameId = Number(row.dataset.gameId);
            row.classList.add("dragging");
            event.dataTransfer.effectAllowed = "move";
        });
        row.addEventListener("dragend", () => {
            row.classList.remove("dragging");
            draggedGameId = null;
            adminTab.querySelectorAll(".admin-game-row").forEach((item) => item.classList.remove("drag-over"));
        });
        row.addEventListener("dragover", (event) => {
            event.preventDefault();
            row.classList.add("drag-over");
        });
        row.addEventListener("dragleave", () => {
            row.classList.remove("drag-over");
        });
        row.addEventListener("drop", async (event) => {
            event.preventDefault();
            row.classList.remove("drag-over");
            const targetId = Number(row.dataset.gameId);
            if (!draggedGameId || draggedGameId === targetId) {
                return;
            }
            const fromIndex = draftGameIds.indexOf(draggedGameId);
            const toIndex = draftGameIds.indexOf(targetId);
            if (fromIndex < 0 || toIndex < 0) {
                return;
            }
            const nextGameIds = [...draftGameIds];
            const [moved] = nextGameIds.splice(fromIndex, 1);
            nextGameIds.splice(toIndex, 0, moved);
            draftGameIds = nextGameIds;
            draftMainGameIds = draftMainGameIds.filter((id) => draftGameIds.includes(id));
            await persistDraftGames();
            setStatus("Порядок игр сохранен.");
        });
    });

    adminTab.querySelectorAll("[data-action]").forEach((button) => {
        button.addEventListener("click", async () => {
            const { action, requestId } = button.dataset;
            try {
                await api(`/api/v1/squads/${squadId}/requests/${requestId}/${action}`, { method: "POST" });
                await renderAdmin();
                if (action === "accept") {
                    me = await api("/api/v1/me");
                    renderShell();
                }
                setStatus("Готово.");
            } catch (error) {
                showErrorToast(error);
            }
        });
    });

    adminTab.querySelectorAll("[data-unblock-id]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await api(`/api/v1/squads/${squadId}/blocked/${button.dataset.unblockId}/unblock`, { method: "POST" });
                await renderAdmin();
                setStatus("Пользователь разблокирован.");
            } catch (error) {
                showErrorToast(error);
            }
        });
    });

    adminTab.querySelectorAll("[data-remove-member]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await api(`/api/v1/squads/${squadId}/members/${button.dataset.removeMember}`, { method: "DELETE" });
                await renderAdmin();
                setStatus("Участник удалён.");
            } catch (error) {
                showErrorToast(error);
            }
        });
    });

    adminTab.querySelectorAll("[data-remove-friend]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await api(`/api/v1/squads/${squadId}/friends/${button.dataset.removeFriend}`, { method: "DELETE" });
                await renderAdmin();
                setStatus("Друг удалён из отряда.");
            } catch (error) {
                showErrorToast(error);
            }
        });
    });
}

async function load() {
    setLoading(true);
    try {
        const previewActive = typeof window.__previewLoad === "function";
        if (!previewActive && !getInitData()) {
            setStatus("Telegram auth data required", true);
            return;
        }

        if (previewActive) {
            await window.__previewLoad();
        } else {
            me = await api("/api/v1/me");
            if (!me?.is_debug_admin && getStoredDebugToken()) {
                clearStoredDebugToken();
            }
            squads = await api("/api/v1/squads");
            launch = resolveLaunchContext(me);
        }

        selectedGameId = me?.default_game_id ?? defaultGameIdForContext();
        appScenario = resolveAppScenario(me, launch);

        if (isRegistered()) {
            showHome();
            hideStatus();
        } else {
            viewHeader.classList.add("hidden");
            mainMenu.classList.add("hidden");
            content.classList.add("hidden");
            contextBanner.classList.add("hidden");
            identityBar?.classList.add("hidden");
            profileControls.classList.add("hidden");
            gameSelectorEl.classList.add("hidden");
            await renderRegistration();
            hideStatus();
        }
    } catch (error) {
        showErrorToast(error);
    } finally {
        setLoading(false);
    }
}

function emptyHtml() {
    return document.querySelector("#empty-template").innerHTML;
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatSquadMemberLabel(member) {
    const gameName = escapeHtml(member.name);
    const displayName = String(member.display_name || "").trim();
    const label = displayName ? `${gameName} - ${escapeHtml(displayName)}` : gameName;
    if (member.is_telegram_admin) {
        return `${label} <span class="admin-badge">Админ</span>`;
    }
    return label;
}

backButton?.addEventListener("click", showHome);
registerButton?.addEventListener("click", registerPlayer);
document.querySelector("#create-squad-button")?.addEventListener("click", createSquad);
document.querySelector("#create-squad-home-button")?.addEventListener("click", showHome);
debugUnlockButton?.addEventListener("click", () => {
    void unlockDebugMode();
});
debugLockButton?.addEventListener("click", () => {
    void lockDebugMode();
});
debugPanelClose?.addEventListener("click", closeDebugPanel);
debugPanel?.addEventListener("click", (event) => {
    if (event.target === debugPanel) {
        closeDebugPanel();
    }
});
debugCodeInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        void unlockDebugMode();
    }
});
setupIdentityNameEasterEgg();
setupSquadPicker();

window.AppShell = {
    load,
    resolveAppScenario,
    resolveLaunchContext,
    renderShell,
    showHome,
    showErrorToast,
    get me() { return me; },
    set me(value) { me = value; },
    get launch() { return launch; },
    set launch(value) { launch = value; },
    get squads() { return squads; },
    set squads(value) { squads = value; },
    get selectedGameId() { return selectedGameId; },
    set selectedGameId(value) { selectedGameId = value; },
    get dockMode() { return dockMode; },
    set dockMode(value) { dockMode = value; },
    get dmActiveSquadId() { return dmActiveSquadId; },
    set dmActiveSquadId(value) { dmActiveSquadId = value; },
};

if (!window.__previewDeferLoad) {
    load();
}
