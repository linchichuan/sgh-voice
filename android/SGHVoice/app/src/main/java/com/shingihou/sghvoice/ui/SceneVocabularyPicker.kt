package com.shingihou.sghvoice.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.processing.DictionaryManager

/** Settings-only scene control; no input-field reads, provider calls or permission changes. */
@Composable
internal fun SceneVocabularyPicker(dictionaryManager: DictionaryManager) {
    var selectedScene by remember(dictionaryManager) { mutableStateOf(dictionaryManager.activeScene) }
    var words by remember(dictionaryManager) { mutableStateOf(dictionaryManager.getSceneCustomWords()) }
    var expanded by remember { mutableStateOf(false) }
    var newWord by remember { mutableStateOf("") }
    var rejected by remember { mutableStateOf(false) }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                stringResource(R.string.scene_vocabulary_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Text(stringResource(R.string.scene_vocabulary_hint), style = MaterialTheme.typography.bodySmall)
            Box {
                OutlinedButton(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.scene_vocabulary_selected, stringResource(sceneLabel(selectedScene))))
                }
                DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    DictionaryManager.SCENE_PRESETS.keys.forEach { sceneId ->
                        DropdownMenuItem(
                            text = { Text(stringResource(sceneLabel(sceneId))) },
                            trailingIcon = {
                                if (selectedScene == sceneId) Icon(Icons.Default.Check, contentDescription = null)
                            },
                            onClick = {
                                dictionaryManager.activeScene = sceneId
                                selectedScene = dictionaryManager.activeScene
                                words = dictionaryManager.getSceneCustomWords()
                                newWord = ""
                                rejected = false
                                expanded = false
                            }
                        )
                    }
                }
            }
            Text(stringResource(sceneDescription(selectedScene)), style = MaterialTheme.typography.bodySmall)
            Text(
                stringResource(R.string.scene_vocabulary_local_privacy),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                OutlinedTextField(
                    value = newWord,
                    onValueChange = { newWord = it; rejected = false },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    label = { Text(stringResource(R.string.scene_vocabulary_add_label)) },
                    isError = rejected,
                    supportingText = {
                        if (rejected) Text(stringResource(R.string.scene_vocabulary_invalid))
                    }
                )
                IconButton(
                    enabled = newWord.isNotBlank(),
                    onClick = {
                        if (dictionaryManager.addSceneCustomWord(newWord, selectedScene)) {
                            words = dictionaryManager.getSceneCustomWords(selectedScene)
                            newWord = ""
                            rejected = false
                        } else {
                            rejected = true
                        }
                    }
                ) { Icon(Icons.Default.Add, contentDescription = stringResource(R.string.scene_vocabulary_add_action)) }
            }
            Text(
                stringResource(R.string.scene_vocabulary_count, words.size, DictionaryManager.MAX_SCENE_CUSTOM_WORDS),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            words.forEach { word ->
                Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(word, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                    IconButton(onClick = {
                        dictionaryManager.removeSceneCustomWord(word, selectedScene)
                        words = dictionaryManager.getSceneCustomWords(selectedScene)
                    }) {
                        Icon(
                            Icons.Default.Delete,
                            contentDescription = stringResource(R.string.scene_vocabulary_delete_action, word)
                        )
                    }
                }
            }
            Text(stringResource(R.string.scene_vocabulary_scope_hint), style = MaterialTheme.typography.bodySmall)
        }
    }
}

private fun sceneLabel(sceneId: String): Int = when (sceneId) {
    "software_development" -> R.string.scene_vocabulary_software
    "business_japanese" -> R.string.scene_vocabulary_business_japanese
    "medical" -> R.string.scene_vocabulary_medical
    else -> R.string.scene_vocabulary_general
}

private fun sceneDescription(sceneId: String): Int = when (sceneId) {
    "software_development" -> R.string.scene_vocabulary_software_description
    "business_japanese" -> R.string.scene_vocabulary_business_description
    "medical" -> R.string.scene_vocabulary_medical_description
    else -> R.string.scene_vocabulary_general_description
}
