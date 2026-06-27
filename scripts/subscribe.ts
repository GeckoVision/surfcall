/**
 * On-chain TxLINE subscribe (free World Cup tier) — founder-gated, mainnet/devnet.
 *
 * Scaffold based on TxODDS' documented flow. Fill the IDL load (from
 * txline-docs .../programs/{mainnet,devnet}.md) and run with a funded keypair.
 *
 *   npm i @solana/web3.js @coral-xyz/anchor @solana/spl-token tweetnacl axios
 *   NETWORK=devnet KEYPAIR=~/.gecko/wallets/gecko-dev.json npx tsx scripts/subscribe.ts
 *
 * Claude does NOT run this (mainnet wallet-signing is yours). Prints jwt + apiToken
 * to paste into surfcall's live Session.
 */
import * as anchor from "@coral-xyz/anchor";
import { Connection, Keypair, PublicKey, SystemProgram } from "@solana/web3.js";
import { TOKEN_2022_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID, getAssociatedTokenAddress } from "@solana/spl-token";
import nacl from "tweetnacl";
import axios from "axios";
import { readFileSync } from "fs";

const NETWORK = process.env.NETWORK === "mainnet" ? "mainnet" : "devnet";
const RPC = NETWORK === "mainnet" ? "https://api.mainnet-beta.solana.com" : "https://api.devnet.solana.com";
const PROGRAM_ID = new PublicKey(
  NETWORK === "mainnet"
    ? "9ExbZjAapQww1vfcisDmrngPinHTEfpjYRWMunJgcKaA"
    : "6pW64gN1s2uqjHkn1unFeEjAwJkPGHoppGvS715wyP2J",
);
const TXL_MINT = new PublicKey(
  NETWORK === "mainnet"
    ? "Zhw9TVKp68a1QrftncMSd6ELXKDtpVMNuMGr1jNwdeL"
    : "4Zao8ocPhmMgq7PdsYWyxvqySMGx7xb9cMftPMkEokRG",
);
const BASE = "https://txline.txodds.com";

const SERVICE_LEVEL_ID = Number(process.env.SERVICE_LEVEL_ID ?? 1); // 1 = 60s delay, 12 = real-time
const DURATION_WEEKS = 4;
const SELECTED_LEAGUES: number[] = [];

async function main() {
  const secret = JSON.parse(readFileSync(process.env.KEYPAIR!, "utf8"));
  const payer = Keypair.fromSecretKey(Uint8Array.from(secret));
  const connection = new Connection(RPC, "confirmed");
  const wallet = new anchor.Wallet(payer);
  const provider = new anchor.AnchorProvider(connection, wallet, { commitment: "confirmed" });

  // TODO: load the IDL from txline-docs .../programs/<network>.md
  const idl = JSON.parse(readFileSync(process.env.IDL ?? "./txline.idl.json", "utf8"));
  const program = new anchor.Program(idl, PROGRAM_ID, provider);

  const [pricingMatrixPda] = PublicKey.findProgramAddressSync([Buffer.from("pricing_matrix")], PROGRAM_ID);
  const [tokenTreasuryPda] = PublicKey.findProgramAddressSync([Buffer.from("token_treasury_v2")], PROGRAM_ID);
  const userTokenAccount = await getAssociatedTokenAddress(TXL_MINT, payer.publicKey, false, TOKEN_2022_PROGRAM_ID);
  const tokenTreasuryVault = await getAssociatedTokenAddress(TXL_MINT, tokenTreasuryPda, true, TOKEN_2022_PROGRAM_ID);

  const txSig = await program.methods
    .subscribe(SERVICE_LEVEL_ID, DURATION_WEEKS)
    .accounts({
      user: payer.publicKey,
      pricingMatrix: pricingMatrixPda,
      tokenMint: TXL_MINT,
      userTokenAccount,
      tokenTreasuryVault,
      tokenTreasuryPda,
      tokenProgram: TOKEN_2022_PROGRAM_ID,
      associatedTokenProgram: ASSOCIATED_TOKEN_PROGRAM_ID,
      systemProgram: SystemProgram.programId,
    })
    .rpc();
  console.log("subscribed, txSig:", txSig);

  const { data: guest } = await axios.post(`${BASE}/auth/guest/start`);
  const jwt = guest.token;
  const msg = new TextEncoder().encode(`${txSig}:${SELECTED_LEAGUES.join(",")}:${jwt}`);
  const sig = Buffer.from(nacl.sign.detached(msg, payer.secretKey)).toString("base64");
  const { data: act } = await axios.post(
    `${BASE}/api/token/activate`,
    { txSig, walletSignature: sig, leagues: SELECTED_LEAGUES },
    { headers: { Authorization: `Bearer ${jwt}` } },
  );
  const apiToken = typeof act === "string" ? act.trim() : act.token;
  console.log("\nPaste into surfcall Session:\n  jwt       =", jwt, "\n  api_token =", apiToken);
}

main().catch((e) => { console.error(e); process.exit(1); });
