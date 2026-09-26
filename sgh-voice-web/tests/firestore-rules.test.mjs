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

function validAndroidRegistration(overrides = {}) {
  return {
    name: "Synthetic Tester",
    email: "synthetic@example.invalid",
    platform: "android",
    version: "2.8.3",
    fileName: "SGHVoice-Android-v2.8.3.apk",
    locale: "en",
    consentVersion: 2,
    riskAcknowledged: true,
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

test("public client can create only the current consented Android release record", async () => {
  const database = testEnvironment.unauthenticatedContext().firestore();
  await assertSucceeds(
    setDoc(doc(database, "sgh-voice-downloads", "valid"), validAndroidRegistration())
  );
});

test("stale consent, wrong artifact, or missing Android risk acknowledgement is denied", async () => {
  const database = testEnvironment.unauthenticatedContext().firestore();

  await assertFails(
    setDoc(
      doc(database, "sgh-voice-downloads", "stale-consent"),
      validAndroidRegistration({ consentVersion: 1 })
    )
  );
  await assertFails(
    setDoc(
      doc(database, "sgh-voice-downloads", "wrong-file"),
      validAndroidRegistration({ fileName: "unapproved.apk" })
    )
  );
  await assertFails(
    setDoc(
      doc(database, "sgh-voice-downloads", "no-risk"),
      validAndroidRegistration({ riskAcknowledged: false })
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
  await assertSucceeds(setDoc(reference, validAndroidRegistration()));
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
      validAndroidRegistration(overrides)));
  }
  const missingEmail = validAndroidRegistration();
  delete missingEmail.email;
  await assertFails(setDoc(doc(database, "sgh-voice-downloads", "missing-email"), missingEmail));
});

test("rolling deployment accepts only matched previous-release metadata", async () => {
  const database = testEnvironment.unauthenticatedContext().firestore();
  await assertSucceeds(setDoc(doc(database, "sgh-voice-downloads", "previous"),
    validAndroidRegistration({ version: "2.8.2", fileName: "SGHVoice-Android-v2.8.2.apk" })));
  await assertFails(setDoc(doc(database, "sgh-voice-downloads", "previous-mismatched"),
    validAndroidRegistration({ version: "2.8.2" })));
  await assertSucceeds(setDoc(doc(database, "sgh-voice-downloads", "cached"),
    validAndroidRegistration({ version: "2.7.9", fileName: "SGHVoice-Android-v2.7.9.apk" })));
  await assertFails(setDoc(doc(database, "sgh-voice-downloads", "mismatched"),
    validAndroidRegistration({ version: "2.7.9" })));
  await assertFails(setDoc(doc(database, "sgh-voice-downloads", "unknown"),
    validAndroidRegistration({ version: "9.9.9", fileName: "SGHVoice-Android-v9.9.9.apk" })));
  await assertFails(setDoc(doc(database, "sgh-voice-downloads", "unpublished"),
    validAndroidRegistration({ version: "2.8.1", fileName: "SGHVoice-Android-v2.8.1.apk" })));
});
