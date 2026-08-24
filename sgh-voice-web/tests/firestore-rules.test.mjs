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
  doc,
  getDoc,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(testDirectory, "..");
let testEnvironment;

function validAndroidRegistration(overrides = {}) {
  return {
    name: "Synthetic Tester",
    email: "synthetic@example.invalid",
    platform: "android",
    version: "2.7.2",
    fileName: "SGHVoice-Android-v2.7.2.apk",
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
