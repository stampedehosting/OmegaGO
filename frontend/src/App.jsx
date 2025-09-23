import { useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Progress } from '@/components/ui/progress.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { 
  Users, 
  TrendingUp, 
  BookOpen, 
  DollarSign, 
  Target, 
  Award,
  Globe,
  Smartphone,
  BarChart3,
  Calendar,
  Mail,
  Phone,
  MapPin,
  Star,
  CheckCircle,
  Clock,
  ArrowRight,
  Zap,
  Shield,
  Headphones
} from 'lucide-react'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('overview')

  // Sample data for the demo
  const agencyStats = {
    totalAgents: 25,
    monthlyRevenue: 125000,
    coursesCompleted: 89,
    avgPerformance: 87
  }

  const topAgents = [
    { name: 'Sarah Johnson', id: 'SJ001', sales: 15, commission: 8500, completion: 100 },
    { name: 'Mike Chen', id: 'MC002', sales: 12, commission: 7200, completion: 95 },
    { name: 'Lisa Rodriguez', id: 'LR003', sales: 11, commission: 6800, completion: 90 }
  ]

  const recentCourses = [
    { title: 'Medicare Basics', category: 'Onboarding', completion: 95, required: true },
    { title: 'Sales Techniques', category: 'Sales', completion: 78, required: false },
    { title: 'Compliance Training', category: 'Compliance', completion: 100, required: true }
  ]

  const features = [
    {
      icon: Users,
      title: 'Agent Management',
      description: 'Comprehensive agent profiles with performance tracking and goal management'
    },
    {
      icon: BookOpen,
      title: 'Training Platform',
      description: 'Interactive courses with progress tracking and certification management'
    },
    {
      icon: Globe,
      title: 'Website Generation',
      description: 'Automated agent websites with lead capture and social media integration'
    },
    {
      icon: BarChart3,
      title: 'Analytics Dashboard',
      description: 'Real-time performance metrics and revenue tracking with forecasting'
    },
    {
      icon: Smartphone,
      title: 'CRM Integration',
      description: 'Seamless integration with MedicarePro and other industry-specific CRMs'
    },
    {
      icon: Zap,
      title: 'Automation',
      description: 'Automated workflows for lead nurturing and social media posting'
    }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  Agency Engine
                </h1>
                <p className="text-sm text-gray-600">Insurance Agent Management Platform</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <Badge variant="secondary" className="bg-green-100 text-green-800">
                <CheckCircle className="w-3 h-3 mr-1" />
                Live Demo
              </Badge>
              <Button className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700">
                Get Started
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <h2 className="text-4xl md:text-6xl font-bold text-gray-900 mb-6">
            Scale Your Insurance Agency with
            <span className="block bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              Intelligent Automation
            </span>
          </h2>
          <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
            Comprehensive platform for managing agents, training, CRM integration, and automated marketing. 
            Built specifically for health insurance agencies like The Independent Life.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700">
              View Live Demo
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <Button size="lg" variant="outline">
              <Headphones className="w-4 h-4 mr-2" />
              Schedule Consultation
            </Button>
          </div>
        </div>
      </section>

      {/* Stats Overview */}
      <section className="py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-blue-600">Total Agents</p>
                    <p className="text-3xl font-bold text-blue-900">{agencyStats.totalAgents}</p>
                  </div>
                  <Users className="w-8 h-8 text-blue-600" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-green-600">Monthly Revenue</p>
                    <p className="text-3xl font-bold text-green-900">
                      ${agencyStats.monthlyRevenue.toLocaleString()}
                    </p>
                  </div>
                  <DollarSign className="w-8 h-8 text-green-600" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-purple-600">Courses Completed</p>
                    <p className="text-3xl font-bold text-purple-900">{agencyStats.coursesCompleted}</p>
                  </div>
                  <BookOpen className="w-8 h-8 text-purple-600" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-orange-600">Avg Performance</p>
                    <p className="text-3xl font-bold text-orange-900">{agencyStats.avgPerformance}%</p>
                  </div>
                  <Target className="w-8 h-8 text-orange-600" />
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Main Dashboard */}
      <section className="py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-4 mb-8">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="agents">Agents</TabsTrigger>
              <TabsTrigger value="training">Training</TabsTrigger>
              <TabsTrigger value="integrations">Integrations</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center">
                      <TrendingUp className="w-5 h-5 mr-2 text-blue-600" />
                      Top Performing Agents
                    </CardTitle>
                    <CardDescription>Monthly performance leaders</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {topAgents.map((agent, index) => (
                        <div key={agent.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                          <div className="flex items-center space-x-3">
                            <div className="w-8 h-8 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-full flex items-center justify-center text-white font-bold text-sm">
                              {index + 1}
                            </div>
                            <div>
                              <p className="font-medium">{agent.name}</p>
                              <p className="text-sm text-gray-600">{agent.id}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="font-bold text-green-600">${agent.commission.toLocaleString()}</p>
                            <p className="text-sm text-gray-600">{agent.sales} sales</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center">
                      <BookOpen className="w-5 h-5 mr-2 text-purple-600" />
                      Training Progress
                    </CardTitle>
                    <CardDescription>Course completion rates</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {recentCourses.map((course, index) => (
                        <div key={index} className="space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              <h4 className="font-medium">{course.title}</h4>
                              {course.required && (
                                <Badge variant="secondary" className="text-xs">Required</Badge>
                              )}
                            </div>
                            <span className="text-sm font-medium">{course.completion}%</span>
                          </div>
                          <Progress value={course.completion} className="h-2" />
                          <p className="text-xs text-gray-600">{course.category}</p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="agents" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Agent Management</CardTitle>
                  <CardDescription>Comprehensive agent profiles and performance tracking</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {topAgents.map((agent) => (
                      <Card key={agent.id} className="border-2 hover:border-blue-300 transition-colors">
                        <CardContent className="p-4">
                          <div className="flex items-center space-x-3 mb-3">
                            <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-full flex items-center justify-center text-white font-bold">
                              {agent.name.split(' ').map(n => n[0]).join('')}
                            </div>
                            <div>
                              <h3 className="font-semibold">{agent.name}</h3>
                              <p className="text-sm text-gray-600">{agent.id}</p>
                            </div>
                          </div>
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-sm text-gray-600">Monthly Sales</span>
                              <span className="font-medium">{agent.sales}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-sm text-gray-600">Commission</span>
                              <span className="font-medium text-green-600">${agent.commission.toLocaleString()}</span>
                            </div>
                            <div className="space-y-1">
                              <div className="flex justify-between">
                                <span className="text-sm text-gray-600">Training</span>
                                <span className="text-sm font-medium">{agent.completion}%</span>
                              </div>
                              <Progress value={agent.completion} className="h-1" />
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="training" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Online Training Platform</CardTitle>
                  <CardDescription>Interactive courses with progress tracking and certifications</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {recentCourses.map((course, index) => (
                      <Card key={index} className="border-2 hover:border-purple-300 transition-colors">
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between mb-3">
                            <h3 className="font-semibold">{course.title}</h3>
                            {course.required ? (
                              <Badge className="bg-red-100 text-red-800">Required</Badge>
                            ) : (
                              <Badge variant="secondary">Optional</Badge>
                            )}
                          </div>
                          <p className="text-sm text-gray-600 mb-3">{course.category}</p>
                          <div className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-sm text-gray-600">Completion Rate</span>
                              <span className="font-medium">{course.completion}%</span>
                            </div>
                            <Progress value={course.completion} className="h-2" />
                          </div>
                          <Button className="w-full mt-3" variant="outline" size="sm">
                            View Course
                          </Button>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="integrations" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>System Integrations</CardTitle>
                  <CardDescription>Connected services and API integrations</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card className="border-2 border-green-200 bg-green-50">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="font-semibold">MedicarePro CRM</h3>
                          <Badge className="bg-green-100 text-green-800">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            Connected
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-600 mb-3">
                          Health insurance CRM with lead management and policy tracking
                        </p>
                        <div className="flex items-center text-sm text-gray-600">
                          <Clock className="w-4 h-4 mr-1" />
                          Last sync: 2 minutes ago
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="border-2 border-green-200 bg-green-50">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="font-semibold">Agent Methods</h3>
                          <Badge className="bg-green-100 text-green-800">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            Connected
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-600 mb-3">
                          Website hosting, design, and social media automation
                        </p>
                        <div className="flex items-center text-sm text-gray-600">
                          <Globe className="w-4 h-4 mr-1" />
                          25 agent websites active
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="border-2 border-blue-200 bg-blue-50">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="font-semibold">Social Media APIs</h3>
                          <Badge className="bg-blue-100 text-blue-800">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            Active
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-600 mb-3">
                          Facebook, LinkedIn, and Instagram automation
                        </p>
                        <div className="flex items-center text-sm text-gray-600">
                          <Smartphone className="w-4 h-4 mr-1" />
                          156 posts scheduled this month
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="border-2 border-purple-200 bg-purple-50">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="font-semibold">Email Marketing</h3>
                          <Badge className="bg-purple-100 text-purple-800">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            Active
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-600 mb-3">
                          Automated email campaigns and lead nurturing
                        </p>
                        <div className="flex items-center text-sm text-gray-600">
                          <Mail className="w-4 h-4 mr-1" />
                          89% open rate this month
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">
              Everything You Need to Scale Your Agency
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Built specifically for health insurance agencies, with deep integration to industry-standard tools
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <Card key={index} className="border-2 hover:border-blue-300 hover:shadow-lg transition-all duration-300">
                <CardContent className="p-6">
                  <div className="w-12 h-12 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center mb-4">
                    <feature.icon className="w-6 h-6 text-white" />
                  </div>
                  <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                  <p className="text-gray-600">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-gradient-to-r from-blue-600 to-indigo-600">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
            Ready to Transform Your Agency?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Join agencies like The Independent Life who are scaling with Agency Engine
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="bg-white text-blue-600 hover:bg-gray-100">
              Schedule Demo Call
              <Calendar className="w-4 h-4 ml-2" />
            </Button>
            <Button size="lg" variant="outline" className="border-white text-white hover:bg-white hover:text-blue-600">
              <Phone className="w-4 h-4 mr-2" />
              Call (330) 351-8697
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-8 h-8 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
                  <Shield className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-xl font-bold">Agency Engine</h3>
              </div>
              <p className="text-gray-400">
                Empowering insurance agencies with intelligent automation and comprehensive management tools.
              </p>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Platform</h4>
              <ul className="space-y-2 text-gray-400">
                <li>Agent Management</li>
                <li>Training Platform</li>
                <li>CRM Integration</li>
                <li>Analytics Dashboard</li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Integrations</h4>
              <ul className="space-y-2 text-gray-400">
                <li>MedicarePro CRM</li>
                <li>Agent Methods</li>
                <li>Social Media APIs</li>
                <li>Email Marketing</li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Contact</h4>
              <div className="space-y-2 text-gray-400">
                <div className="flex items-center">
                  <Phone className="w-4 h-4 mr-2" />
                  (330) 351-8697
                </div>
                <div className="flex items-center">
                  <Mail className="w-4 h-4 mr-2" />
                  hello@agencyengine.com
                </div>
                <div className="flex items-center">
                  <MapPin className="w-4 h-4 mr-2" />
                  Stampede Hosting
                </div>
              </div>
            </div>
          </div>
          
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2025 Agency Engine by Stampede Hosting. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App
