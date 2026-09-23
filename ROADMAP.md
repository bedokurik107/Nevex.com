# NEVEX roadmap

1. Catalog/backend scaffold — this package.
2. Connect existing React cards to `/api/gifts`.
3. Add Telegram media URLs and real Model/Pattern images.
4. Render Backdrop from Telegram's official color data.
5. Real filters/sorting/search.
6. Telegram Mini App initialization and server-side `initData` validation.
7. Users and Telegram IDs.
8. Ownership synchronization.
9. Wallet/transaction architecture.
10. Production deployment and bot integration.

Security rule:
Never put Telegram API hash, bot token or other secrets into React/frontend code.
Telegram says Mini App `initDataUnsafe` must not be trusted; `initData` should be validated on the backend before using Telegram identity.
