pipeline {
    agent none

    environment {
        // Credentials
        DOCKERHUB_CREDS = credentials('dockerhub_delmas')
        GITHUB_TOKEN    = credentials('GITHUB_TOKEN')

        // Docker Hub
        REGISTRY_NAMESPACE = "delmas007"

        IMAGE_NAME_DEV  = "market-place-b2b"
        IMAGE_NAME_PROD = "marketplace-b2b-back-ci-cd-prod"

        IMAGE_TAG = "latest"

        AUTH_URL = "https://Arnold-Freelance:${GITHUB_TOKEN}@github.com/Arnold-Freelance/marketplace-b2b-back-ci-cd.git"
    }

    stages {

        stage('Détecter la branche') {
            agent any

            steps {

                script {

                    def branch = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ""

                    echo "Branche : ${branch}"

                    if (branch.contains("dev")) {

                        env.BRANCHE = "dev"
                        env.SHOULD_RUN = "true"
                        env.IMAGE_NAME = env.IMAGE_NAME_DEV
                        env.HELM_BRANCH = "helm-dev"

                    }

                    else if (branch.contains("prod")) {

                        env.BRANCHE = "prod"
                        env.SHOULD_RUN = "true"
                        env.IMAGE_NAME = env.IMAGE_NAME_PROD
                        env.HELM_BRANCH = "helm-prod"

                    }

                    else {

                        env.SHOULD_RUN = "false"

                        echo "Pipeline ignoré."

                    }

                }

            }

        }

        stage("Version") {

            when {

                expression { env.SHOULD_RUN == "true" }

            }

            agent any

            steps {

                script {

                    env.BUILDVERSION = UUID.randomUUID().toString()

                    echo env.BUILDVERSION

                }

            }

        }

        stage("Build Docker") {

            when {

                expression { env.SHOULD_RUN == "true" }

            }

            agent any

            steps {

                sh """

                docker build \
                    --network=host \
                    -t ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG} \
                    -t ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${BUILDVERSION} \
                    .

                """

            }

        }

        stage("Smoke Test") {

            when {

                expression { env.SHOULD_RUN == "true" }

            }

            agent any

            steps {

                sh """

                docker rm -f ${IMAGE_NAME} || true

                docker run -d \
                    --name ${IMAGE_NAME} \
                    -e PORT=8000 \
                    -p 8000:8000 \
                    ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}

                sleep 20

                curl --fail http://localhost:8000/api/docs

                """

            }

        }

        stage("Push Docker + GitOps") {

            when {

                expression { env.SHOULD_RUN == "true" }

            }

            agent any

            steps {

                sh """

                echo "$DOCKERHUB_CREDS_PSW" | docker login \
                    -u "$DOCKERHUB_CREDS_USR" \
                    --password-stdin

                docker push ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}

                docker push ${REGISTRY_NAMESPACE}/${IMAGE_NAME}:${BUILDVERSION}

                docker logout

                rm -rf marketplace-b2b-back-ci-cd

                git clone ${AUTH_URL}

                cd marketplace-b2b-back-ci-cd

                git fetch --all --prune

                if git show-ref --verify --quiet refs/remotes/origin/${HELM_BRANCH}
                then
                    git checkout -B ${HELM_BRANCH} origin/${HELM_BRANCH}
                else
                    git checkout -B ${HELM_BRANCH}
                fi

                git config user.email "angamancedrick@gmail.com"
                git config user.name "delmas007"

                if [ "${BRANCHE}" = "dev" ]; then
                    VALUES_FILE="helm/marketplace-b2b-back-ci-cd-dev/values.yaml"
                else
                    VALUES_FILE="helm/marketplace-b2b-back-ci-cd/values.yaml"
                fi

                echo "Modification de ${VALUES_FILE}"

                sed -i "s/^  tag:.*/  tag: ${BUILDVERSION}/" "${VALUES_FILE}"

                git add "${VALUES_FILE}"

                if git diff --cached --quiet; then
                    echo "Aucun changement Helm."
                else
                    git commit -m "chore(${HELM_BRANCH}): update image to ${BUILDVERSION}"
                    git push origin ${HELM_BRANCH}
                fi

                """

            }

        }

    }

    post {

        success {

            script {

                slackSend(

                    channel: "#notification-jenkins-back",

                    color: "good",

                    message: """
                                :white_check_mark: BUILD OK

                                Projet : ${env.JOB_NAME}

                                Branche : ${env.BRANCHE}

                                Build : #${env.BUILD_NUMBER}

                                Image :

                                ${env.REGISTRY_NAMESPACE}/${env.IMAGE_NAME}:${env.BUILDVERSION}

                                ${env.BUILD_URL}
                            """

                )

            }

        }

        failure {

            script {

                slackSend(

                    channel: "#notification-jenkins-back",

                    color: "danger",

                    message: """
                                :x: BUILD ECHEC

                                Projet : ${env.JOB_NAME}

                                Branche : ${env.BRANCHE}

                                Build : #${env.BUILD_NUMBER}

                                ${env.BUILD_URL}
                            """

                )

            }

        }

        always {

            always {
                    node('contrôleur') {
                        sh '''
                            echo "Nettoyage Docker..."
                            docker rm -f ${IMAGE_NAME} || true
                            docker image prune -f || true
                        '''
                    }
                }

        }

    }

}