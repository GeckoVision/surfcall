# Going live — the on-chain subscribe (founder-gated)

The demo runs in **recorded mode ($0)** with no subscription. To get **live World Cup
data**, you do a one-time on-chain `subscribe` (free tier = no TxL tokens, just gas),
then activate → apiToken. The Python access layer (`gecko/access.py`) already
handles guest-JWT → activate; this step is only the on-chain `subscribe` that
produces the `txSig`.

> ⚠️ This is a **mainnet, wallet-signing** action. Claude does not run it. You do.

## Real on-chain values (from txline-docs … /programs/addresses.md)
| | Mainnet | Devnet |
|---|---|---|
| TxLINE program | `9ExbZjAapQww1vfcisDmrngPinHTEfpjYRWMunJgcKaA` | `6pW64gN1s2uqjHkn1unFeEjAwJkPGHoppGvS715wyP2J` |
| TxL token mint | `Zhw9TVKp68a1QrftncMSd6ELXKDtpVMNuMGr1jNwdeL` | `4Zao8ocPhmMgq7PdsYWyxvqySMGx7xb9cMftPMkEokRG` |
| Token program | Token-2022 | Token-2022 |

**PDA seeds:** Token Treasury = `"token_treasury_v2"`, Pricing Matrix = `"pricing_matrix"` (derive against the program ID above). Full IDL/types: txline-docs … `/programs/mainnet.md` (or `/devnet.md`).

## Steps
1. **Wallet + funds.** Use a dedicated keypair (not your OKX main wallet — its TEE key can't do the local message-sign the activation needs). Generate one and **fund it from your OKX agentic wallet** with ~0.01 SOL (gas + a Token-2022 ATA rent). For a *devnet* dry-run, use `~/.gecko/wallets/gecko-dev.json` + `solana airdrop`.
2. **Subscribe** (free tier): run `scripts/subscribe.ts` with `SERVICE_LEVEL_ID=1` (60s delay) or `12` (real-time), `DURATION_WEEKS=4`. It loads the IDL, derives the PDAs, sends `subscribe(...)`, prints the `txSig`. *(Free tier transfers no TxL — only network gas.)*
3. **Activate**: the same script (or `gecko/access.py::establish_session`) does guest-JWT → sign `txSig:leagues:jwt` → `/api/token/activate` → **apiToken**.
4. **Flip Gecko to live**: construct a `Session(jwt=<jwt>, api_token=<apiToken>)` and pass it to `AgentApiClient(spec, session=...)`, then call with `mode="live"`. The demo's recorded data becomes real World Cup data — same code path.

## Cost
- Devnet dry-run: **$0** (airdrop).
- Mainnet: **a few cents of SOL** (gas + one-time ATA rent). No payment to TxODDS; the World Cup tiers are free.
