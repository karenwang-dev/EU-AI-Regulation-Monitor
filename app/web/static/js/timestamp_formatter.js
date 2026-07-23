/**
 * Shared timestamp formatter for the dashboard.
 * Parses UTC-aware ISO timestamps and legacy naive UTC values,
 * then displays them in the browser's local timezone.
 */
(function (global, exportsObject) {
    const OFFSET_PATTERN = /(?:[zZ]|[+-]\d{2}:\d{2})$/;

    function parseTimestamp(value) {
        if (value === null || value === undefined) {
            return null;
        }
        const trimmed = String(value).trim();
        if (!trimmed) {
            return null;
        }

        let candidate = trimmed;
        if (!OFFSET_PATTERN.test(trimmed)) {
            candidate = trimmed.includes("T")
                ? `${trimmed}Z`
                : `${trimmed.replace(" ", "T")}Z`;
        }

        const parsed = new Date(candidate);
        if (Number.isNaN(parsed.getTime())) {
            return null;
        }
        return parsed;
    }

    function pad(value) {
        return String(value).padStart(2, "0");
    }

    function formatPartsInTimeZone(parsed, timeZone) {
        const formatter = new Intl.DateTimeFormat("en-GB", {
            timeZone,
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        });
        const parts = formatter.formatToParts(parsed);
        const lookup = Object.fromEntries(
            parts
                .filter((part) => part.type !== "literal")
                .map((part) => [part.type, part.value])
        );
        return {
            yyyy: lookup.year,
            mm: lookup.month,
            dd: lookup.day,
            hh: lookup.hour,
            min: lookup.minute,
        };
    }

    function formatTimestamp(value, options = {}) {
        const parsed = parseTimestamp(value);
        if (!parsed) {
            return options.fallback ?? "—";
        }

        let yyyy;
        let mm;
        let dd;
        let hh;
        let min;

        if (options.timeZone) {
            const parts = formatPartsInTimeZone(parsed, options.timeZone);
            yyyy = parts.yyyy;
            mm = parts.mm;
            dd = parts.dd;
            hh = parts.hh;
            min = parts.min;
        } else {
            yyyy = String(parsed.getFullYear());
            mm = pad(parsed.getMonth() + 1);
            dd = pad(parsed.getDate());
            hh = pad(parsed.getHours());
            min = pad(parsed.getMinutes());
        }

        const base = `${yyyy}-${mm}-${dd} ${hh}:${min}`;

        if (options.showTimezone === false) {
            return base;
        }

        const localeOptions = { timeZoneName: "short" };
        if (options.timeZone) {
            localeOptions.timeZone = options.timeZone;
        }

        const parts = parsed
            .toLocaleTimeString(undefined, localeOptions)
            .split(" ");
        const tz = parts.length > 1 ? parts[parts.length - 1] : "";
        return tz ? `${base} ${tz}` : base;
    }

    function applyLocalTimestamps(root) {
        if (typeof document === "undefined") {
            return;
        }

        const scope = root || document;
        scope.querySelectorAll("[data-timestamp]").forEach((element) => {
            const raw = element.getAttribute("data-timestamp");
            const showTimezone = element.getAttribute("data-show-tz") !== "false";
            const formatted = formatTimestamp(raw, { showTimezone });
            element.textContent = formatted;
            const parsed = parseTimestamp(raw);
            if (parsed) {
                element.setAttribute("datetime", parsed.toISOString());
            }
        });
    }

    global.parseTimestamp = parseTimestamp;
    global.formatTimestamp = formatTimestamp;
    global.applyLocalTimestamps = applyLocalTimestamps;

    if (exportsObject) {
        exportsObject.parseTimestamp = parseTimestamp;
        exportsObject.formatTimestamp = formatTimestamp;
        exportsObject.applyLocalTimestamps = applyLocalTimestamps;
    }
})(
    typeof window !== "undefined" ? window : globalThis,
    typeof module !== "undefined" ? module.exports : null
);
