# Changelog

All notable changes to this project will be documented in this file.

## [1.0.7] - 2024-12-17

### Added
- Microphone permission request button when no devices are available
- Better error handling for device-related errors (NotFoundError)
- Graceful error messages for connection failures

### Fixed
- Fixed "NotFoundError: Requested device not found" crash by adding proper error handling
- DeviceSelector now shows a permission request button instead of empty dropdown when no mics are available

## [1.0.6] - 2024-12-17

### Added
- WebSocket connection to obtain Daily room credentials dynamically
- New `VITE_WEBSOCKET_URL` environment variable for configuring the WebSocket endpoint (defaults to `ws://0.0.0.0:8765`)
- WebSocket error display in the UI with styled error message
- Automatic cleanup of WebSocket connection on disconnect

### Changed
- Modified `connectbot` function to first connect to WebSocket server
- Room URL and token are now received from WebSocket server instead of being hardcoded
- The Daily client connection is now established after receiving credentials from WebSocket

### Technical
- Added `useState` and `useRef` hooks for WebSocket state management
- WebSocket reference stored in `useRef` to persist across renders

## [1.0.5] - 2024-12-17

### Fixed
- Fixed TypeScript error "Cannot find name 'process'" by adding `"node"` to the `types` array in `tsconfig.app.json`

## [1.0.4] - 2024-12-17

### Changed
- Updated `.app-container` to have full viewport dimensions (`width: 100%` and `height: 100vh`)
- Added `justify-content: center` to `.app-container` for vertical centering

## [1.0.3] - 2024-12-17

### Added
- New **Media Tracks** display component showing real-time audio track information
- Displays both local (user) and AI bot audio tracks side by side
- Shows track status (LIVE/OFF), track ID, enabled state, and muted state
- Live audio level meters with animated progress bars
- Real-time audio level analysis using Web Audio API
- Visual indicators with color-coded tracks (cyan for user, purple for AI)
- Responsive grid layout that stacks on smaller screens

### Changed
- Updated `MediaTrack.tsx` from a placeholder to a fully functional component
- Added new `MediaTrack.css` with matching glassmorphism styling
- Integrated MediaTracks component into the connected state view in Bot.tsx

## [1.0.2] - 2024-12-17

### Changed
- Made the entire layout more compact to fit on smaller screens without scrolling
- Increased card max-width from 480px to 600px for better content display
- Enabled vertical scrolling on body (changed `overflow: hidden` to `overflow-y: auto`)
- Reduced all padding, margins, and gaps throughout the UI
- Made the orb animation smaller (140px → 80px)
- Made the idle state icon smaller (120px → 80px)
- Reduced font sizes across all components for a more compact look
- Reduced root padding from 2rem to 1rem

## [1.0.1] - 2024-12-17

### Fixed
- Fixed DeviceSelector component not being visible when connected
- Added `display: block` to `.device-selector-label` to make it render properly
- Added proper styling to `.device-selector-section` with padding, background, and border to match other UI sections

## [1.0.0] - 2024-12-17

### Added
- Complete UI/UX redesign with modern dark theme
- Beautiful glassmorphism card effects with backdrop blur
- Connection status indicator with animated dot and state labels
- Transport status display showing real-time connection state
- Animated idle state with floating microphone icon and pulse effect
- Connecting state with spinning animation
- Connected state with animated glowing orb
- Dual audio visualizer showing both user ("You") and AI voice activity
- Custom styled microphone toggle with iOS-style switch
- Modern dropdown device selector with custom styling
- Animated background with drifting particles
- Smooth fade-in-up animations on load
- Responsive design optimized for mobile and desktop

### Changed
- Replaced default Vite styling with custom "Deep Space" theme
- Updated font family to 'Outfit' for modern typography
- Improved button styling with gradient backgrounds and hover effects
- Enhanced visual hierarchy with proper spacing and typography scale
- Updated page title to "Prediqt AI"

### Design Features
- Color palette: Deep dark backgrounds with cyan/teal accents
- Glassmorphism effects with semi-transparent cards
- Animated pulse rings and glow effects
- Custom CSS animations (pulse, float, shimmer, rotate)
- Subtle background particle animation
- Modern border radius and shadow treatments

