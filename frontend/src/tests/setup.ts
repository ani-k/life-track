// Global test setup for jsdom environment
import { vi } from 'vitest'

// Stub fetch globally so composable tests don't hit the network
const fetchMock = vi.fn()
global.fetch = fetchMock

export { fetchMock }
