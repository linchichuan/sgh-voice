package com.shingihou.sghvoice.ime

import android.content.Context
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.channels.FileChannel

internal data class ZhuyinSparseIndexEntry(
    val key: String,
    val byteOffset: Int
)

internal data class IndexedZhuyinRow(
    val key: String,
    val entries: List<ZhuyinLexiconEntry>
)

internal fun parseZhuyinSparseIndex(text: String): List<ZhuyinSparseIndexEntry> {
    val entries = text.lineSequence()
        .filter { it.isNotBlank() && !it.startsWith("#") }
        .map { line ->
            val separator = line.lastIndexOf('\t')
            require(separator > 0) { "Malformed Zhuyin sparse index row." }
            val key = line.substring(0, separator)
            val offset = line.substring(separator + 1).toIntOrNull()
            require(offset != null && offset >= 0) { "Invalid Zhuyin sparse index offset." }
            ZhuyinSparseIndexEntry(key, offset)
        }
        .toList()

    entries.zipWithNext().forEach { (first, second) ->
        require(first.key < second.key) { "Zhuyin sparse index keys must be sorted." }
        require(first.byteOffset < second.byteOffset) {
            "Zhuyin sparse index offsets must be increasing."
        }
    }
    return entries
}

/**
 * Reads sorted lexicon rows through a sparse byte-offset index.
 *
 * The production buffer is a read-only memory map of an uncompressed APK
 * asset. Queries duplicate the buffer cursor, so the mapped data never needs
 * to be copied into a large heap Map and concurrent reads do not share state.
 */
internal class IndexedZhuyinReader(
    private val data: ByteBuffer,
    private val sparseIndex: List<ZhuyinSparseIndexEntry>
) {
    companion object {
        private const val MAX_INDEX_SEEK_ROWS = 128
    }

    fun lookupExact(key: String): List<ZhuyinLexiconEntry> {
        if (key.isEmpty() || data.limit() == 0) return emptyList()
        var offset = floorOffset(key)
        var scannedRows = 0
        while (offset < data.limit() && scannedRows < MAX_INDEX_SEEK_ROWS) {
            val (nextOffset, row) = readRow(offset) ?: break
            when {
                row.key == key -> return row.entries
                row.key > key -> return emptyList()
            }
            offset = nextOffset
            scannedRows += 1
        }
        return emptyList()
    }

    fun lookupPrefix(prefix: String, maxRows: Int): List<IndexedZhuyinRow> {
        if (prefix.isEmpty() || maxRows <= 0 || data.limit() == 0) return emptyList()
        val result = mutableListOf<IndexedZhuyinRow>()
        var offset = floorOffset(prefix)
        var scannedRows = 0
        val scanLimit = MAX_INDEX_SEEK_ROWS + maxRows
        while (
            offset < data.limit() &&
            result.size < maxRows &&
            scannedRows < scanLimit
        ) {
            val (nextOffset, row) = readRow(offset) ?: break
            when {
                row.key.startsWith(prefix) -> result += row
                row.key > prefix -> break
            }
            offset = nextOffset
            scannedRows += 1
        }
        return result
    }

    private fun floorOffset(target: String): Int {
        if (sparseIndex.isEmpty()) return 0
        var low = 0
        var high = sparseIndex.size
        while (low < high) {
            val middle = (low + high).ushr(1)
            if (sparseIndex[middle].key <= target) {
                low = middle + 1
            } else {
                high = middle
            }
        }
        return sparseIndex[(low - 1).coerceAtLeast(0)].byteOffset
    }

    private fun readRow(offset: Int): Pair<Int, IndexedZhuyinRow>? {
        if (offset !in 0 until data.limit()) return null
        var end = offset
        while (end < data.limit() && data.get(end) != '\n'.code.toByte()) {
            end += 1
        }
        if (end == offset) return null

        val bytes = ByteArray(end - offset)
        data.duplicate().apply {
            position(offset)
            get(bytes)
        }
        val line = bytes.toString(Charsets.UTF_8)
        val separator = line.indexOf('\t')
        if (separator <= 0) return null
        val key = line.substring(0, separator)
        val entries = line.substring(separator + 1)
            .split('|')
            .mapNotNull { encoded ->
                val scoreSeparator = encoded.lastIndexOf(':')
                if (scoreSeparator <= 0) return@mapNotNull null
                val text = encoded.substring(0, scoreSeparator)
                val score = encoded.substring(scoreSeparator + 1).toIntOrNull()
                    ?: return@mapNotNull null
                if (text.isBlank()) null else ZhuyinLexiconEntry(text, score)
            }
        val nextOffset = if (end < data.limit()) end + 1 else end
        return nextOffset to IndexedZhuyinRow(key, entries)
    }
}

internal class IndexedZhuyinAsset(
    context: Context,
    private val dataAssetPath: String,
    private val indexAssetPath: String
) {
    private val assets = context.applicationContext.assets
    private val reader: IndexedZhuyinReader by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        val indexText = assets.open(indexAssetPath).bufferedReader(Charsets.UTF_8).use {
            it.readText()
        }
        val mappedData = assets.openFd(dataAssetPath).use { descriptor ->
            FileInputStream(descriptor.fileDescriptor).channel.use { channel ->
                channel.map(
                    FileChannel.MapMode.READ_ONLY,
                    descriptor.startOffset,
                    descriptor.length
                )
            }
        }
        IndexedZhuyinReader(mappedData, parseZhuyinSparseIndex(indexText))
    }

    fun lookupExact(key: String): List<ZhuyinLexiconEntry> = reader.lookupExact(key)

    fun lookupPrefix(prefix: String, maxRows: Int): List<IndexedZhuyinRow> =
        reader.lookupPrefix(prefix, maxRows)

    fun warmUp() {
        reader
    }
}
