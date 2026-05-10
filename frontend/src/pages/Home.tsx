import { useNavigate } from "react-router-dom"
import { Button } from "../components/ui/Button"
import { Card, CardHeader, CardTitle, CardDescription } from "../components/ui/Card"

export default function Home() {
  const navigate = useNavigate()

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
          <Button size="lg" onClick={() => navigate('/dashboard')}>Get Started</Button>
          <Button variant="outline" size="lg" onClick={() => navigate('/datasets')}>Learn More</Button>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="cursor-pointer hover:border-primary transition-colors" onClick={() => navigate('/query')}>
          <CardHeader>
            <CardTitle>Data Analysis</CardTitle>
            <CardDescription>Analyze your data with AI-powered insights</CardDescription>
          </CardHeader>
        </Card>
        <Card className="cursor-pointer hover:border-primary transition-colors" onClick={() => navigate('/dashboard')}>
          <CardHeader>
            <CardTitle>Forecasting</CardTitle>
            <CardDescription>Predict trends with machine learning</CardDescription>
          </CardHeader>
        </Card>
        <Card className="cursor-pointer hover:border-primary transition-colors" onClick={() => navigate('/datasets')}>
          <CardHeader>
            <CardTitle>Visualization</CardTitle>
            <CardDescription>Create interactive charts and reports</CardDescription>
          </CardHeader>
        </Card>
      </section>
    </div>
  )
}