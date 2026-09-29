import { after, before, beforeEach, test } from "node:test";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from "@firebase/rules-unit-testing";
import {
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  serverTimestamp,
  setDoc,
  updateDoc,
} from "firebase/firestore";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(testDirectory, "..");
let testEnvironment;

function validMacOSRegistration(overrides = {}) {
  return {
    name: "Synthetic Tester",
    email: "synthetic@example.invalid",
    platform: "macos",
    version: "2.6.0",
    fileName: "SGH.Voice-2.6.0-apple-silicon.dmg",
    locale: "en",
    consentVersion: 2,
    riskAcknowledged: false,
    createdAt: serverTimestamp(),
    ...overrides,
  };
}

before(async () => {
  const rules = await readFile(path.join(webRoot, "firestore.rules"), "utf8");
  testEnvironment = await initializeTestEnvironment({
    projectId: "demo-sgh-voice-release",
    firestore: { rules },
  });
});

beforeEach(async () => {
  await testEnvironment.clearFirestore();
});

after(async () => {
  await testEnvironment.cleanup();
});

test("public client can still create the current consented macOS release record", async () => {
  const database = testEnvironment.unauthenticatedContext().firestore();
  await assertSucceeds(
    setDoc(doc(database, "sgh-voice-downloads", "valid"), validMacOSRegistration())
  );
});

test("stale consent, wrong artifact, or wrong macOS risk acknowledgement is denied", async () => {
  const database = testEnvironment.unauthenticatedContext().firestore();

  await assertFails(
    setDoc(
      doc(database, "sgh-voice-downloads", "stale-consent"),
      validMacOSRegistration({ consentVersion: 1 })
    )
  );
  await assertFails(
    setDoc(
      doc(database, "sgh-voice-downloads", "wrong-file"),
      validMacOSRegistration({ fileName: "unapproved.apk" })
    )
  );
  await assertFails(
    setDoc(
      doc(database, "sgh-voice-downloads", "no-risk"),
      validMacOSRegistration({ riskAcknowledged: true })
    )
  );
});

test("public clients cannot read download registrations", async () => {
  const database = testEnvironment.unauthenticatedContext().firestore();
  await assertFails(getDoc(doc(database, "sgh-voice-downloads", "private")));
});

test("registrations cannot be listed, updated or deleted by public clients", async () => {
  const database = testEnvironment.unauthenticatedContext().firestore();
  const reference = doc(database, "sgh-voice-downloads", "immutable");
  await assertSucceeds(setDoc(reference, validMacOSRegistration()));
  await assertFails(getDocs(collection(database, "sgh-voice-downloads")));
  await assertFails(updateDoc(reference, { name: "Changed" }));
  await assertFails(deleteDoc(reference));
});

test("current release still denies malformed, oversized and privilege fields", async () => {
  const database = testEnvironment.unauthenticatedContext().firestore();
  const invalidCases = [
    { name: "x".repeat(101) },
    { email: "x".repeat(250) + "@example.invalid" },
    { name: 42 },
    { createdAt: "2026-09-26" },
    { createdAt: new Date("2020-01-01T00:00:00Z") },
    { isAdmin: true },
    { ownerId: "other-user" },
    { fileName: "../SGHVoice-Android-v2.8.3.apk" },
  ];
  for (const [index, overrides] of invalidCases.entries()) {
    await assertFails(setDoc(doc(database, "sgh-voice-downloads", `invalid-${index}`),
      validMacOSRegistration(overrides)));
  }
  const missingEmail = validMacOSRegistration();
  delete missingEmail.email;
  await assertFails(setDoc(doc(database, "sgh-voice-downloads", "missing-email"), missingEmail));
});

test("cached Android downloads fail closed at every previous and current version", async () => {
  const database = testEnvironment.unauthenticatedContext().firestore();
  for (const version of ["2.7.9", "2.8.2", "2.8.3", "2.8.4", "9.9.9"]) {
    await assertFails(setDoc(doc(database, "sgh-voice-downloads", version),
      validMacOSRegistration({ platform: "android", version, fileName: `SGHVoice-Android-v${version}.apk`, riskAcknowledged: true })));
  }
});

const application = (overrides = {}) => ({
  name: "Synthetic Tester", email: "synthetic@example.invalid", platform: "android",
  track: "alpha", status: "pending", locale: "en", consentVersion: 1,
  privacyConsent: true, testingCommitment: true, createdAt: serverTimestamp(), ...overrides,
});

test("anonymous applicant can create only a pending Alpha application", async () => {
  const db = testEnvironment.unauthenticatedContext().firestore();
  for (const locale of ["ja", "zh", "en"]) {
    await assertSucceeds(setDoc(doc(db, "sgh-voice-alpha-applications", locale), application({ locale })));
  }
});

test("applicant cannot grant eligibility, send mail, change track or bypass consent", async () => {
  const db = testEnvironment.unauthenticatedContext().firestore();
  for (const [i, overrides] of [
    { status: "approved" }, { status: "invited" }, { emailSent: true }, { isAdmin: true },
    { track: "internal" }, { platform: "macos" }, { privacyConsent: false },
    { privacyConsent: "true" }, { testingCommitment: false }, { testingCommitment: "true" },
    { consentVersion: 0 }, { consentVersion: "1" },
  ].entries()) {
    await assertFails(setDoc(doc(db, "sgh-voice-alpha-applications", `invalid-${i}`), application(overrides)));
  }
});

test("application fields are bounded, typed, complete and server-timestamped", async () => {
  const db = testEnvironment.unauthenticatedContext().firestore();
  for (const [i, overrides] of [
    { name: "" }, { name: "   " }, { name: 42 }, { name: "x".repeat(101) },
    { email: "not-an-email" }, { email: "a b@example.invalid" },
    { email: "x".repeat(250) + "@example.invalid" }, { email: 42 }, { locale: "unknown" },
    { createdAt: "2026-09-30" }, { createdAt: new Date("2020-01-01") },
  ].entries()) {
    await assertFails(setDoc(doc(db, "sgh-voice-alpha-applications", `invalid-${i}`), application(overrides)));
  }
  for (const key of Object.keys(application())) {
    const incomplete = application();
    delete incomplete[key];
    await assertFails(setDoc(doc(db, "sgh-voice-alpha-applications", `missing-${key}`), incomplete));
  }
});

test("applications cannot be read, listed, updated, overwritten or deleted by clients", async () => {
  const db = testEnvironment.unauthenticatedContext().firestore();
  await assertSucceeds(setDoc(doc(db, "sgh-voice-alpha-applications", "private"), application()));
  for (const context of [testEnvironment.unauthenticatedContext(), testEnvironment.authenticatedContext("arbitrary-user")]) {
    const database = context.firestore();
    const ref = doc(database, "sgh-voice-alpha-applications", "private");
    await assertFails(getDoc(ref));
    await assertFails(getDocs(collection(database, "sgh-voice-alpha-applications")));
    await assertFails(updateDoc(ref, { status: "invited" }));
    await assertFails(setDoc(ref, application()));
    await assertFails(deleteDoc(ref));
  }
});
