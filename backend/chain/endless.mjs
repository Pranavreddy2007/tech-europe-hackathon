#!/usr/bin/env node
// Thin CLI over the Endless TS SDK, called by govmind/services/blockchain.py.
//   node endless.mjs balance <address>
//   node endless.mjs transfer <recipient> <amount_octas>
//   node endless.mjs audit
// Prints one JSON object on stdout; errors go to stderr with a non-zero exit.

import fs from "node:fs";
import {
  Account,
  AccountAddress,
  Ed25519PrivateKey,
  Endless,
  EndlessConfig,
  Network,
} from "@endlesslab/endless-ts-sdk";

const network = process.env.ENDLESS_NETWORK === "mainnet" ? Network.MAINNET : Network.TESTNET;
const endless = new Endless(new EndlessConfig({ network }));

function parseAddress(input) {
  if (input.startsWith("0x") || /^[0-9a-fA-F]+$/.test(input)) return AccountAddress.fromString(input);
  return AccountAddress.fromBs58String(input);
}

// Like the original GovMind: without ENDLESS_PRIVATE_KEY, generate a testnet account once,
// fund it from the faucet, and keep the key in ENDLESS_KEY_FILE so the address stays stable.
async function agentAccount() {
  const key = process.env.ENDLESS_PRIVATE_KEY;
  if (key) return Account.fromPrivateKey({ privateKey: new Ed25519PrivateKey(key) });

  const keyFile = process.env.ENDLESS_KEY_FILE;
  if (!keyFile) throw new Error("ENDLESS_PRIVATE_KEY is not set — on-chain writes are disabled");
  let account;
  if (fs.existsSync(keyFile)) {
    account = Account.fromPrivateKey({ privateKey: new Ed25519PrivateKey(fs.readFileSync(keyFile, "utf8").trim()) });
  } else {
    if (network === Network.MAINNET) throw new Error("Refusing to auto-generate a mainnet account");
    account = Account.generate();
    fs.writeFileSync(keyFile, account.privateKey.toString(), { mode: 0o600 });
  }
  // Fund once from the testnet faucet; the marker file means it succeeded (retried after an outage).
  const funded = `${keyFile}.funded`;
  if (!fs.existsSync(funded) && network !== Network.MAINNET) {
    await fund(account);
    fs.writeFileSync(funded, new Date().toISOString());
  }
  return account;
}

async function fund(account) {
  const tx = await endless.fundAccount({ signer: account });
  await endless.waitForTransaction({ transactionHash: tx.hash });
}

async function submit(signer, transaction) {
  const pending = await endless.signAndSubmitTransaction({ signer, transaction });
  const result = await endless.waitForTransaction({ transactionHash: pending.hash });
  return { tx_hash: pending.hash, success: result.success ?? true, sender: signer.accountAddress.toBs58String() };
}

const [cmd, ...args] = process.argv.slice(2);

const commands = {
  async balance([address]) {
    const raw = await endless.getAccountEDSAmount({ accountAddress: parseAddress(address) });
    return { balance_raw: raw.toString() };
  },
  async transfer([recipient, octas]) {
    const sender = await agentAccount();
    const transaction = await endless.transferEDS({
      sender,
      recipient: parseAddress(recipient),
      amount: Number(octas),
    });
    return submit(sender, transaction);
  },
  async audit() {
    const sender = await agentAccount();
    const transaction = await endless.transaction.build.simple({
      sender: sender.accountAddress,
      data: {
        function: "0x1::endless_account::transfer",
        typeArguments: [],
        functionArguments: [sender.accountAddress, 1],
      },
    });
    return submit(sender, transaction);
  },
  async address() {
    const account = await agentAccount();
    const raw = await endless.getAccountEDSAmount({ accountAddress: account.accountAddress });
    return { address: account.accountAddress.toBs58String(), balance_raw: raw.toString() };
  },
  async faucet() {
    const account = await agentAccount();
    await fund(account);
    return { address: account.accountAddress.toBs58String() };
  },
};

try {
  if (!commands[cmd]) throw new Error(`unknown command: ${cmd}`);
  process.stdout.write(JSON.stringify(await commands[cmd](args)));
} catch (err) {
  process.stderr.write(`${err?.message ?? err}\n`);
  process.exit(1);
}
