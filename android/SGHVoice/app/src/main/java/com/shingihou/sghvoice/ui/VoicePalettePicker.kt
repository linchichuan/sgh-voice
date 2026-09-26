package com.shingihou.sghvoice.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.VoicePalette

/** Light swatches with visible names and selected semantics, not color alone. */
@Composable
@OptIn(ExperimentalMaterial3Api::class)
fun VoicePalettePicker(selected: VoicePalette, onSelect: (VoicePalette) -> Unit) {
    val ink = Color(0xFF25372F)
    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.Transparent)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(
                    modifier = Modifier.size(64.dp).background(Brush.radialGradient(
                        0f to Color(selected.argb), 0.48f to Color(selected.argb).copy(alpha = 0.9f),
                        0.78f to Color(selected.argb).copy(alpha = 0.39f), 1f to Color(selected.argb).copy(alpha = 0f)
                    ), CircleShape), contentAlignment = Alignment.Center
                ) {
                    Icon(Icons.Default.Mic, contentDescription = null, tint = ink, modifier = Modifier.size(28.dp))
                }
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.voice_palette_title), style = MaterialTheme.typography.titleMedium)
                    Text(stringResource(R.string.voice_palette_hint), style = MaterialTheme.typography.bodySmall)
                }
            }
            VoicePalette.entries.chunked(2).forEach { row ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    row.forEach { palette ->
                        FilterChip(
                            selected = selected == palette,
                            border = null,
                            onClick = { onSelect(palette) },
                            modifier = Modifier.weight(1f).heightIn(min = 48.dp),
                            label = { Text(stringResource(paletteLabel(palette))) },
                            leadingIcon = if (selected == palette) {
                                { Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(18.dp)) }
                            } else null,
                            colors = FilterChipDefaults.filterChipColors(
                                containerColor = Color(palette.argb), selectedContainerColor = Color(palette.argb),
                                labelColor = ink, selectedLabelColor = ink, selectedLeadingIconColor = ink
                            )
                        )
                    }
                }
            }
        }
    }
}

private fun paletteLabel(palette: VoicePalette): Int = when (palette) {
    VoicePalette.MINT -> R.string.voice_palette_mint
    VoicePalette.SKY -> R.string.voice_palette_sky
    VoicePalette.LAVENDER -> R.string.voice_palette_lavender
    VoicePalette.PEACH -> R.string.voice_palette_peach
    VoicePalette.ROSE -> R.string.voice_palette_rose
    VoicePalette.SAND -> R.string.voice_palette_sand
}
