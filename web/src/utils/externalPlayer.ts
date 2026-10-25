/**
 * Hand a video URL to a locally installed player (VLC and similar).
 *
 * Every path here avoids creating files on the client:
 * - Android: intent:// deep link handled by VLC, no download.
 * - iOS/iPadOS: VideoLAN's documented x-callback stream action (never download).
 * - Desktop: the browser cannot launch apps, so copy the URL (or an optional M3U).
 */

export type PlayerPlatform = 'desktop' | 'android' | 'ios'

export const buildRawUrl = (imageId: number) =>
  `${window.location.origin}/api/images/${imageId}/raw`

export const detectPlatform = (): PlayerPlatform => {
  const ua = navigator.userAgent || ''
  if (/android/i.test(ua)) return 'android'
  const isIPad = /macintosh/i.test(ua) && navigator.maxTouchPoints > 1
  if (/iphone|ipad|ipod/i.test(ua) || isIPad) return 'ios'
  return 'desktop'
}

/**
 * intent://<host[:port]><path>#Intent;scheme=...;type=video/*;package=org.videolan.vlc;end
 * The port must be kept: LAN deployments are usually on :5000/:5173, not :80.
 */
export const buildAndroidVlcIntent = (rawUrl: string, title?: string) => {
  const url = new URL(rawUrl)
  const scheme = url.protocol.replace(':', '')
  const parts = [
    `intent://${url.host}${url.pathname}${url.search}` +
      `#Intent;scheme=${scheme};type=video/*;package=org.videolan.vlc`
  ]
  if (title) parts.push(`S.title=${encodeURIComponent(title)}`)
  parts.push('end')
  return parts.join(';')
}

/** Documented VLC for iOS path; `stream` only, no file is written to the device. */
export const buildIosVlcStream = (rawUrl: string) =>
  `vlc-x-callback://x-callback-url/stream?url=${encodeURIComponent(rawUrl)}`

/** Version-dependent fallback for VLC iOS 2.3+; not the primary path. */
export const buildVlcScheme = (rawUrl: string) => `vlc://${rawUrl}`

export const copyPlayUrl = async (rawUrl: string) => {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(rawUrl)
      return true
    }
  } catch {
    // Fall through to the legacy copy path.
  }

  const textarea = document.createElement('textarea')
  textarea.value = rawUrl
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '-1000px'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()

  let copied = false
  try {
    copied = document.execCommand('copy')
  } catch {
    copied = false
  }
  document.body.removeChild(textarea)
  return copied
}

const safeFileName = (fileName: string, imageId: number) => {
  const base = (fileName || '').replace(/\.[^./\\]+$/, '')
  const cleaned = base.replace(/[\\/:*?"<>|]/g, '_').trim().slice(0, 80)
  return cleaned || `video-${imageId}`
}

/** Tiny text playlist, generated only on click and revoked right after the download starts. */
export const downloadM3U = (imageId: number, fileName: string) => {
  const rawUrl = buildRawUrl(imageId)
  const content = `#EXTM3U\n#EXTINF:-1,${fileName}\n${rawUrl}\n`
  const blob = new Blob([content], { type: 'audio/x-mpegurl' })
  const objectUrl = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = objectUrl
  link.download = `${safeFileName(fileName, imageId)}.m3u`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

export const downloadOriginal = (imageId: number, fileName: string) => {
  const link = document.createElement('a')
  link.href = `/api/images/${imageId}/download`
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/**
 * Open the video in the platform's player. Must be called synchronously from a
 * user gesture, otherwise Safari blocks the navigation.
 * Returns the platform used; 'desktop' means the caller should copy the URL.
 */
export const openInVlc = (imageId: number, title?: string): PlayerPlatform => {
  const rawUrl = buildRawUrl(imageId)
  const platform = detectPlatform()

  if (platform === 'android') {
    window.location.href = buildAndroidVlcIntent(rawUrl, title)
    return platform
  }
  if (platform === 'ios') {
    window.location.href = buildIosVlcStream(rawUrl)
    return platform
  }
  return 'desktop'
}
