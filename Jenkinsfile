pipeline {
    agent none

    tools {
        maven 'M3'
    }

    environment {
        // Credentials
        DOCKERHUB_CREDS = credentials('dockerhub_delmas')
        GITHUB_TOKEN    = credentials('GITHUB_TOKEN')

        // Registry
        REGISTRY_NAMESPACE = "delmas007"

        // Images
        IMAGE_NAME_DEV  = "market-place-b2b"
        IMAGE_NAME_PROD = "marketplace-b2b-back-ci-cd-prod"
        IMAGE_TAG = "latest"

        // Repo Helm (GitOps)
        AUTH_URL = "https://Arnold-Freelance:${GITHUB_TOKEN}@github.com/Arnold-Freelance/marketplace-b2b-back-ci-cd.git"

    }

    stages {

        stage('Détecter la branche et configurer Helm') {
            agent any
            steps {
                script {
                    def branch = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ""
                    echo "Branche détectée : ${branch}"

                    if (branch.contains('dev')) {
                        env.BRANCHE = 'dev'
                        env.SHOULD_RUN     = 'true'
                        env.IMAGE_NAME    = env.IMAGE_NAME_DEV
                        env.HELM_BRANCH   = 'helm-dev'
                    }
                    else if (branch.contains('prod')) {
                        env.BRANCHE = 'prod'
                        env.SHOULD_RUN     = 'true'
                        env.IMAGE_NAME    = env.IMAGE_NAME_PROD
                        env.HELM_BRANCH   = 'helm-prod'
                    }
                    else {
                        env.SHOULD_RUN = 'false'
                        echo "Pipeline SKIPPÉ : branche non supportée"
                    }

                    echo """
                    SHOULD_RUN   = ${env.SHOULD_RUN}
                    IMAGE_NAME   = ${env.IMAGE_NAME}
                    HELM_BRANCH  = ${env.HELM_BRANCH}
                    """
                }
            }
        }

        stage('Générer la version (UUID)') {
            when { expression { env.SHOULD_RUN == 'true' } }
            agent any
            steps {
                script {
                    env.BUILDVERSION = UUID.randomUUID().toString()
                    echo "Version image : ${env.BUILDVERSION}"
                }
            }
        }

        stage('Build Docker Image') {
          agent any
          steps {
            sh '''
            mvn clean package -DskipTests

              docker build --network=host \
                -t ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG} \
                -t ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${BUILDVERSION} \
                .
            '''
          }
        }


        stage('Test rapide du conteneur') {
            when { expression { env.SHOULD_RUN == 'true' } }
            agent any
            steps {
                sh """
                    docker rm -f ${IMAGE_NAME} || true

                    docker run -d --name ${IMAGE_NAME} \\
                      -p 18084:8084 \\
                      -e PORT=8084 \\
                      ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}
                """
            }
        }

        stage('Push Docker + Mise à jour Helm (GitOps)') {
            when { expression { env.SHOULD_RUN == 'true' } }
            agent any
            steps {
                sh """
                    echo "$DOCKERHUB_CREDS_PSW" | docker login -u "$DOCKERHUB_CREDS_USR" --password-stdin

                    docker push ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}
                    docker push ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${BUILDVERSION}

                    docker logout || true

                    rm -rf marketplace-b2b-back-ci-cd
                    git clone "$AUTH_URL" marketplace-b2b-back-ci-cd
                    cd marketplace-b2b-back-ci-cd

                    git fetch --all --prune

                    if git show-ref --verify --quiet refs/remotes/origin/${HELM_BRANCH}; then
                      git checkout -B ${HELM_BRANCH} origin/${HELM_BRANCH}
                    else
                      git checkout -B ${HELM_BRANCH}
                    fi

                    git config user.email "angamancedrick@gmail.com"
                    git config user.name  "delmas007"

                    sed -i "/image.tag/{n;s/.*/                  value: ${BUILDVERSION}/}" helm/marketplace-b2b-back-ci-cd/templates/Application_cd marketplace-b2b-back-ci-cd_${BRANCHE}.yaml

                    if git diff --quiet; then
                      echo "Aucun changement Helm."
                    else
                      git add helm/marketplace-b2b-back-ci-cd/templates/Application_marketplace-b2b-back-ci-cd_${BRANCHE}.yaml
                      git commit -m "chore(${HELM_BRANCH}): update image to ${BUILDVERSION}"
                      git push "$AUTH_URL" ${HELM_BRANCH}:${HELM_BRANCH}
                    fi
                """
            }
        }
    }

    post {
            success {
                script {
                    def duration = currentBuild.durationString.replace(' and counting', '')

                    slackSend(
                        channel: '#notification-jenkins-back',
                        color: 'good',
                        message: """
                        :white_check_mark: *BUILD BACK RÉUSSI*

                        *Projet*   : ${env.JOB_NAME}
                        *Branche*  : ${env.BRANCHE}
                        *Build*    : #${env.BUILD_NUMBER}
                        *Durée*    : ${duration}

                        *Image Docker* :
                        `${env.REGISTRY_NAMESPACE}/${env.IMAGE_NAME}:${env.BUILDVERSION}`

                        🔗 *Lien Jenkins* :
                        <${env.BUILD_URL}|Voir le build>
                        """
                    )
                }
            }

            failure {
                script {
                    def duration = currentBuild.durationString.replace(' and counting', '')

                    slackSend(
                        channel: '#notification-jenkins-back',
                        color: 'danger',
                        message: """
                              :x: *BUILD BACK ÉCHOUÉ*

                              *Projet*   : ${env.JOB_NAME}
                              *Branche*  : ${env.BRANCHE ?: 'unknown'}
                              *Build*    : #${env.BUILD_NUMBER}
                              *Durée*    : ${duration}

                              🔗 *Lien Jenkins* :
                              <${env.BUILD_URL}|Voir le build>
                              """
                    )
                }
            }

            always {
                script {
                    if (env.IMAGE_NAME) {
                        node {
                            sh '''
                                echo "Nettoyage Docker..."
                                docker rm -f $IMAGE_NAME || true
                                docker image prune -f || true
                            '''
                        }
                    } else {
                        echo "Pas de nettoyage (pipeline ignoré)."
                    }
                }
            }
        }
}