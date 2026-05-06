import { Button } from "../components/ui/Button"
import { Card, CardHeader, CardTitle, CardDescription } from "../components/ui/Card"

export function Home() {
  return (
    <div className="space-y-8">
      <section className="text-center py-12">
        <h1 className="text-4xl font-bold tracking-tight mb-4">
          Forge Intelligence
        </h1>
        <p className="text-xl text-muted-foreground mb-8">
          AI-Powered Analytics Platform
        </p>
        <div className="flex justify-center gap-4">
          <Button size="lg">Get Started</Button>
          <Button variant="outline" size="lg">Learn More</Button>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Data Analysis</CardTitle>
            <CardDescription>Analyze your data with AI-powered insights</CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Forecasting</CardTitle>
            <CardDescription>Predict trends with machine learning</CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Visualization</CardTitle>
            <CardDescription>Create interactive charts and reports</CardDescription>
          </CardHeader>
        </Card>
      </section>
    </div>
  )
}
