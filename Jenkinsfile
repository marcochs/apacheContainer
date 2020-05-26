pipeline {
  agent any
  stages {
    stage('workspace') {
      steps {
        ws(dir: 'workdir') {
          git(url: 'https://github.com/marcochs/apacheContainer.git', branch: 'dev', poll: true)
        }

        ws(dir: 'workspace')
      }
    }

  }
  environment {
    env = 'dev'
  }
}