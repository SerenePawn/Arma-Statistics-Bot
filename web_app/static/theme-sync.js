(function initThemeSync(global) {
    const THEME_DEFAULTS = {
        light: {
            bg: "#f3f4f6",
            text: "#111827",
            hint: "#6b7280",
            card: "#ffffff",
            button: "#2481cc",
            buttonText: "#ffffff",
        },
        dark: {
            bg: "#111827",
            text: "#f9fafb",
            hint: "#9ca3af",
            card: "#1f2937",
            button: "#2ea6ff",
            buttonText: "#ffffff",
        },
    };

    function normalizeHex(color) {
        if (!color) {
            return null;
        }
        let value = String(color).trim();
        if (!value.startsWith("#")) {
            value = `#${value}`;
        }
        if (value.length === 4) {
            value = `#${value[1]}${value[1]}${value[2]}${value[2]}${value[3]}${value[3]}`;
        }
        return /^#[0-9a-f]{6}$/i.test(value) ? value.toLowerCase() : null;
    }

    function hexToRgb(hex) {
        const normalized = normalizeHex(hex);
        if (!normalized) {
            return null;
        }
        const value = Number.parseInt(normalized.slice(1), 16);
        return {
            r: (value >> 16) & 255,
            g: (value >> 8) & 255,
            b: value & 255,
        };
    }

    function rgbToHex({ r, g, b }) {
        return `#${[r, g, b]
            .map((channel) => Math.round(channel).toString(16).padStart(2, "0"))
            .join("")}`;
    }

    function mixHex(colorA, colorB, weightA) {
        const a = hexToRgb(colorA);
        const b = hexToRgb(colorB);
        if (!a || !b) {
            return colorA || colorB;
        }
        const weight = Math.max(0, Math.min(1, weightA));
        return rgbToHex({
            r: a.r * weight + b.r * (1 - weight),
            g: a.g * weight + b.g * (1 - weight),
            b: a.b * weight + b.b * (1 - weight),
        });
    }

    function resolveScheme() {
        const tg = global.Telegram?.WebApp;
        if (tg?.colorScheme === "light" || tg?.colorScheme === "dark") {
            return tg.colorScheme;
        }
        return global.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function resolveCard(bg, card, scheme) {
        const normalizedBg = normalizeHex(bg);
        const normalizedCard = normalizeHex(card);
        if (normalizedCard && normalizedCard !== normalizedBg) {
            return normalizedCard;
        }
        return scheme === "dark"
            ? mixHex("#ffffff", bg, 0.14)
            : mixHex("#000000", bg, 0.05);
    }

    function applyDerivedSurfaces(root, text, card) {
        root.style.setProperty("--border-subtle", mixHex(text, card, 0.2));
        root.style.setProperty("--border-faint", mixHex(text, card, 0.14));
        root.style.setProperty("--border-soft", mixHex(text, card, 0.16));
        root.style.setProperty("--border-strong", mixHex(text, card, 0.24));
        root.style.setProperty("--surface-raised", mixHex(text, card, 0.16));
        root.style.setProperty("--surface-ghost", mixHex(text, card, 0.12));
        root.style.setProperty("--surface-muted", mixHex(text, card, 0.09));
        root.style.setProperty("--surface-faint", mixHex(text, card, 0.06));
        root.style.setProperty("--input-bg", mixHex(text, card, 0.1));
        root.style.setProperty("--highlight-top", mixHex(text, card, 0.1));
        root.style.setProperty("--highlight-strong", mixHex(text, card, 0.22));
    }

    function syncAppTheme() {
        const tg = global.Telegram?.WebApp;
        const scheme = resolveScheme();
        const defaults = THEME_DEFAULTS[scheme];
        const params = tg?.themeParams ?? {};
        const root = global.document.documentElement;

        root.dataset.colorScheme = scheme;

        const bg = normalizeHex(params.bg_color) ?? defaults.bg;
        const text = normalizeHex(params.text_color) ?? defaults.text;
        const hint = normalizeHex(params.hint_color) ?? defaults.hint;
        const button = normalizeHex(params.button_color) ?? defaults.button;
        const buttonText = normalizeHex(params.button_text_color) ?? defaults.buttonText;
        const card = resolveCard(
            bg,
            params.section_bg_color || params.secondary_bg_color || defaults.card,
            scheme,
        );

        root.style.setProperty("--bg", bg);
        root.style.setProperty("--text", text);
        root.style.setProperty("--hint", hint);
        root.style.setProperty("--card", card);
        root.style.setProperty("--button", button);
        root.style.setProperty("--button-text", buttonText);
        root.style.colorScheme = scheme;

        applyDerivedSurfaces(root, text, card);
    }

    global.syncAppTheme = syncAppTheme;
    syncAppTheme();

    const tg = global.Telegram?.WebApp;
    if (tg?.onEvent) {
        tg.onEvent("themeChanged", syncAppTheme);
    }
})(window);
