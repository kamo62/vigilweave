const ORIGIN_HOST = 'vw205ba0c1web.z16.web.core.windows.net'
const API_HOST = 'api.vigilweave.com'
const NO_CACHE_HEADERS = {
  'cache-control': 'no-store, no-cache, must-revalidate, max-age=0',
  pragma: 'no-cache',
}

addEventListener('fetch', (event) => {
  event.respondWith(handleRequest(event.request))
})

function isSpaRoute(pathname) {
  if (pathname === '/') return true
  const lastSegment = pathname.split('/').pop() || ''
  return !lastSegment.includes('.')
}

async function fetchFromOrigin(request, pathname) {
  const url = new URL(request.url)
  url.protocol = 'https:'
  url.hostname = ORIGIN_HOST
  url.port = ''
  url.pathname = pathname

  return fetch(new Request(url.toString(), request), {
    cf: {
      cacheEverything: request.method === 'GET',
    },
  })
}

async function fetchFromApi(request) {
  const url = new URL(request.url)
  url.protocol = 'https:'
  url.hostname = API_HOST
  url.port = ''

  return fetch(new Request(url.toString(), request), {
    cf: {
      cacheEverything: false,
    },
  })
}

async function handleRequest(request) {
  const incomingUrl = new URL(request.url)

  if (incomingUrl.pathname.startsWith('/api/')) {
    return fetchFromApi(request)
  }

  const originResponse = await fetchFromOrigin(request, incomingUrl.pathname)

  if (originResponse.status !== 404 || !isSpaRoute(incomingUrl.pathname)) {
    return withResponseHeaders(originResponse)
  }

  const spaResponse = await fetchFromOrigin(request, '/index.html')
  return withResponseHeaders(spaResponse, 200)
}

function withResponseHeaders(response, status = response.status) {
  const headers = new Headers(response.headers)
  for (const [key, value] of Object.entries(NO_CACHE_HEADERS)) {
    headers.set(key, value)
  }
  return new Response(response.body, {
    status,
    headers,
  })
}
