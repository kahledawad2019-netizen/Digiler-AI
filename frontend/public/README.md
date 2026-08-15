# Static assets

Place the **Digiler AI logo** here, unmodified, as:

```
public/logo.png
```

It is consumed as-is (no recolouring, cropping, or filters) by:

- the sidebar header (`components/logo.tsx`)
- the login screen
- the browser tab favicon (`app/layout.tsx` → `icons: "/logo.png"`)

A square PNG (e.g. 512×512) with a transparent background is recommended.
Until the file is added, the logo slot renders empty — the app is otherwise fully functional.
