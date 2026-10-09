package com.shingihou.sghvoice.ime.manual

import java.util.Locale

/**
 * Small, curated everyday vocabulary for offline prefix completion.
 *
 * This is an explicit suggestion source, not autocorrect. It stores no input,
 * learns nothing, and performs no network or disk access. The host must suppress
 * candidate queries/display in password and no-suggestion editors.
 */
object LocalEnglishCandidateProvider : EnglishCandidateProvider {
    // Common conversational words come first; order is a stable preference,
    // not a claimed corpus frequency or a downloaded third-party dictionary.
    private val words = """
        the to and a of in is it you that for on with this be are have not at
        hello help thanks thank please good morning afternoon evening night
        yes no okay sorry welcome goodbye see soon today tomorrow yesterday
        me my we our your they their he she his her them us an as by from or
        can could would should will want need like know think understand
        do does did done don't doesn't didn't doing make made get got give
        go going gone come coming came take taken put let tell say said ask
        about after again all also always any around back because before
        between both but call change check clear close continue create day
        down each early easy else end enough even every example few find
        first follow found free friend friends full great happy hard here
        home hope how if important inside into just keep kind last late
        later leave left less life little live long look lot love many may
        maybe mean message more most much must name near never new next nice
        now number off old once one only open other out over own part people
        person place plan point problem question quick really reply right
        same send sent show small so some something start still stop sure
        talk team than then there these thing things time together too try
        two under up use used very wait way week well what when where which
        while who why work working works worked world write writing wrong
        year yet you're you've you'll we're we've we'll they're they've
        there's that's it's isn't wasn't weren't can't won't wouldn't
        shouldn't couldn't haven't hasn't hadn't I'm I've I'll I'd
        able accept account action add address agree almost already another
        answer anyone anything appointment available away beautiful begin
        best better big book bring build business busy buy calendar camera
        cancel car care case chat children choose city class clean client
        code coffee color company complete computer confirm contact copy
        correct cost country course customer date dear decide delivery
        design detail details different difficult dinner direction discuss
        document download drive during edit email enjoy enter error event
        everyone everything excellent family favorite feedback feel file
        final finish finished fine flight food form forward Friday future
        general glad group guide happen health hear helpful high history
        holiday hospital hotel hour house however idea image information
        input instead internet invite issue job join key keyboard language
        learn learning letter line link list local location login lunch
        manage map meeting member minute mobile Monday money month move
        music necessary news note nothing notice office online option order
        page paper parent password patient payment phone photo picture
        possible prefer prepare pretty previous price process product
        project provide public purchase quality read ready reason receive
        recent record remember remove report request response result return
        review room run safe Saturday save schedule school search second
        select service set setting settings share short sign simple since
        software someone sometimes sound speak special status stay step
        store street strong student study success Sunday support system
        task test text through Thursday ticket title together travel true
        Tuesday type update upload useful user value version video view
        visit voice walk watch water weather website Wednesday weekend
        welcome window without word worry written yes yourself zero
        January February March April May June July August September October
        November December English Japanese Chinese Japan Taiwan Tokyo
    """.trimIndent().split(Regex("\\s+"))
        .map { it.lowercase(Locale.ROOT) }
        .distinct()

    override fun candidates(prefix: String, limit: Int): List<EnglishCandidate> {
        if (limit <= 0 || prefix.isBlank()) return emptyList()
        val normalized = prefix.lowercase(Locale.ROOT)
        return words.asSequence()
            .withIndex()
            .filter { (_, word) -> word.length > normalized.length && word.startsWith(normalized) }
            .take(limit)
            .map { (index, word) -> EnglishCandidate(text = word, score = words.size - index) }
            .toList()
    }
}
