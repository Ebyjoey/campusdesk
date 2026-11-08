// Declarative pipeline: test -> build image -> push -> deploy to Kubernetes -> smoke test.
// Jenkins runs on the EC2 host with Docker and kubectl installed (installed by Ansible).
//
// Jenkins credentials required (Manage Jenkins -> Credentials):
//   dockerhub-creds : Username with password  (Docker Hub user + access token)
//   kubeconfig      : Secret file             (k3s kubeconfig, server = https://10.20.1.20:6443)
pipeline {
  agent any

  triggers { pollSCM('H/2 * * * *') }

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '15'))
    timeout(time: 25, unit: 'MINUTES')
  }

  environment {
    IMAGE_NAME = 'campusdesk'
    NODE_IP    = '10.20.1.20'   // any k3s node; NodePort 30080 is open on all of them
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.GIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
          env.IMAGE_TAG = "${env.BUILD_NUMBER}-${env.GIT_SHORT}"
        }
      }
    }

    stage('Test') {
      steps {
        // Tests run inside a throwaway Python container, so the host needs no Python.
        sh '''
          docker run --rm -v "$WORKSPACE":/src -w /src python:3.12-slim sh -c \
            "pip install -q -r requirements-dev.txt && \
             pytest --cov=app --cov-report=term --cov-fail-under=80 --junitxml=test-results.xml"
        '''
      }
      post { always { junit allowEmptyResults: true, testResults: 'test-results.xml' } }
    }

    stage('Build image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                          usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''
            docker build -t "$DH_USER/$IMAGE_NAME:$IMAGE_TAG" -t "$DH_USER/$IMAGE_NAME:latest" .
          '''
        }
      }
    }

    stage('Push image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                          usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''
            echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin
            docker push "$DH_USER/$IMAGE_NAME:$IMAGE_TAG"
            docker push "$DH_USER/$IMAGE_NAME:latest"
            docker logout
          '''
        }
      }
    }

    stage('Deploy to Kubernetes') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                          usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS'),
                         file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
          sh '''
            kubectl apply -f k8s/namespace.yaml
            kubectl apply -f k8s/configmap.yaml
            sed "s|__IMAGE__|$DH_USER/$IMAGE_NAME:$IMAGE_TAG|g" k8s/deployment.yaml | kubectl apply -f -
            kubectl -n campusdesk rollout status deployment/campusdesk-web --timeout=180s
          '''
        }
      }
    }

    stage('Smoke test') {
      steps {
        sh '''
          for i in 1 2 3 4 5 6; do
            if curl -fsS "http://$NODE_IP:30080/healthz"; then echo; exit 0; fi
            sleep 5
          done
          echo "Smoke test failed"; exit 1
        '''
      }
    }
  }

  post {
    failure {
      withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
        sh 'kubectl -n campusdesk rollout undo deployment/campusdesk-web || true'
      }
    }
    always { sh 'docker image prune -f || true' }
  }
}
