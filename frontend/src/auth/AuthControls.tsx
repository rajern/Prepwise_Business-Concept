import {
  type AccountInfo,
  type IPublicClientApplication,
  InteractionRequiredAuthError,
  InteractionStatus,
} from '@azure/msal-browser'
import { useIsAuthenticated, useMsal } from '@azure/msal-react'
import { useEffect, useState } from 'react'

import { fetchCurrentUser } from '../api/me'
import { acquireApiAccessToken, createLoginRequest } from './token'
import { reportAuthError } from './diagnostics'

interface AuthControlsProps {
  apiScope: string
}

type TokenStatus = 'loading' | 'ready' | 'interaction-required' | 'error'

export function AuthControls({ apiScope }: AuthControlsProps) {
  const { accounts, inProgress, instance } = useMsal()
  const isAuthenticated = useIsAuthenticated()
  const account = instance.getActiveAccount() ?? accounts[0] ?? null
  const interactionInProgress = inProgress !== InteractionStatus.None

  if (!isAuthenticated || !account) {
    return (
      <SignedOutControls
        apiScope={apiScope}
        instance={instance}
        interactionInProgress={interactionInProgress}
      />
    )
  }

  return (
    <SignedInControls
      key={account.homeAccountId}
      account={account}
      apiScope={apiScope}
      instance={instance}
      interactionInProgress={interactionInProgress}
    />
  )
}

interface SignedOutControlsProps extends AuthControlsProps {
  instance: IPublicClientApplication
  interactionInProgress: boolean
}

function SignedOutControls({
  apiScope,
  instance,
  interactionInProgress,
}: SignedOutControlsProps) {
  const [interactionError, setInteractionError] = useState(false)

  function signIn() {
    setInteractionError(false)
    void instance.loginRedirect(createLoginRequest(apiScope)).catch((error) => {
      reportAuthError('login redirect', error)
      setInteractionError(true)
    })
  }

  return (
    <div className="auth-controls">
      <button
        className="auth-button"
        type="button"
        disabled={interactionInProgress}
        onClick={signIn}
      >
        Sign in or create account
      </button>
      {interactionError && (
        <p className="auth-status auth-status--error" role="alert">
          Sign-in could not be started. Please try again.
        </p>
      )}
    </div>
  )
}

interface SignedInControlsProps extends AuthControlsProps {
  account: AccountInfo
  instance: IPublicClientApplication
  interactionInProgress: boolean
}

function SignedInControls({
  account,
  apiScope,
  instance,
  interactionInProgress,
}: SignedInControlsProps) {
  const [tokenStatus, setTokenStatus] = useState<TokenStatus>('loading')
  const [interactionError, setInteractionError] = useState(false)

  useEffect(() => {
    if (interactionInProgress) {
      return
    }

    let cancelled = false

    void acquireApiAccessToken(instance, account, apiScope)
      .then(fetchCurrentUser)
      .then(() => {
        if (!cancelled) {
          setTokenStatus('ready')
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return
        }

        setTokenStatus(
          error instanceof InteractionRequiredAuthError
            ? 'interaction-required'
            : 'error',
        )
      })

    return () => {
      cancelled = true
    }
  }, [account, apiScope, instance, interactionInProgress])

  function requestApiAccess() {
    setInteractionError(false)
    void instance
      .acquireTokenRedirect({
        ...createLoginRequest(apiScope),
        account,
      })
      .catch((error) => {
        reportAuthError('API access redirect', error)
        setInteractionError(true)
      })
  }

  function signOut() {
    setInteractionError(false)
    void instance
      .logoutRedirect({
        account,
        postLogoutRedirectUri: new URL('/', window.location.origin).toString(),
      })
      .catch((error) => {
        reportAuthError('logout redirect', error)
        setInteractionError(true)
      })
  }

  return (
    <div className="auth-controls auth-controls--signed-in">
      <div>
        <p className="auth-account">{account.name ?? account.username}</p>
        <p className="auth-status" aria-live="polite">
          {tokenStatus === 'loading' && 'Preparing secure API access…'}
          {tokenStatus === 'ready' && 'Signed in · API access ready'}
          {tokenStatus === 'interaction-required' &&
            'Additional confirmation is required for API access.'}
          {tokenStatus === 'error' &&
            'API access could not be prepared. Please try again.'}
        </p>
      </div>
      {tokenStatus === 'interaction-required' && (
        <button
          className="auth-button auth-button--secondary"
          type="button"
          disabled={interactionInProgress}
          onClick={requestApiAccess}
        >
          Continue
        </button>
      )}
      <button
        className="auth-button auth-button--secondary"
        type="button"
        disabled={interactionInProgress}
        onClick={signOut}
      >
        Sign out
      </button>
      {interactionError && (
        <p className="auth-status auth-status--error" role="alert">
          Authentication could not be completed. Please try again.
        </p>
      )}
    </div>
  )
}
