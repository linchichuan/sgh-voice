window.SGH_FIRESTORE_READY = Promise.all([
    import("https://www.gstatic.com/firebasejs/11.4.0/firebase-app.js"),
    import("https://www.gstatic.com/firebasejs/11.4.0/firebase-firestore.js")
]).then(([firebaseApp, firestore]) => {
    const firebaseConfig = {
        apiKey: "AIzaSyCRPasthxWYq3AST2fgbcHZwFc0ce5BABs",
        authDomain: "sgh-meishi.firebaseapp.com",
        projectId: "sgh-meishi",
        storageBucket: "sgh-meishi.firebasestorage.app",
        messagingSenderId: "257956480322",
        appId: "1:257956480322:web:6d4575724e6bb6403474db",
        measurementId: "G-N6VJ1VDTE3"
    };

    const app = firebaseApp.initializeApp(firebaseConfig);
    const db = firestore.getFirestore(app);

    return {
        db,
        addDoc: firestore.addDoc,
        collection: firestore.collection,
        serverTimestamp: firestore.serverTimestamp
    };
});
