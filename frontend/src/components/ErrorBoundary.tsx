import { Component, ReactNode, ErrorInfo } from "react"
import { Button } from "./ui/Button"
import { Card, CardContent } from "./ui/Card"

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen flex items-center justify-center p-4">
          <Card className="max-w-md w-full">
            <CardContent className="pt-6">
              <div className="text-center space-y-4">
                <h1 className="text-2xl font-bold text-destructive">Something went wrong</h1>
                <p className="text-muted-foreground">
                  We encountered an unexpected error. Please try refreshing the page.
                </p>
                {this.state.error && (
                  <p className="text-xs text-muted-foreground bg-muted p-2 rounded">
                    {this.state.error.message}
                  </p>
                )}
                <div className="flex gap-2 justify-center">
                  <Button onClick={this.handleReset}>
                    Try Again
                  </Button>
                  <Button variant="outline" onClick={() => window.location.href = "/"}>
                    Go Home
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}